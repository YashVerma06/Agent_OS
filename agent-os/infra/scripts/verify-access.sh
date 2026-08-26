#!/usr/bin/env bash
#
# Agent OS - deployment access verification
#
# Run this in Google Cloud Shell AFTER the owner completes infra/OWNER_SETUP.md.
# It measures what the calling identity can actually do, rather than trusting
# the Console or an assumption about what roles/editor includes.
#
#   bash agent-os/infra/scripts/verify-access.sh
#
# Read-only and free. It creates nothing, deletes nothing, and never reads a
# secret value. The one live API call is Vertex AI countTokens, which is not
# billed.
#
# Exit codes: 0 = every required check passed, 1 = at least one failed.

set -uo pipefail

PROJECT="${GOOGLE_CLOUD_PROJECT:-agent-os-506220}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
RUNTIME_SA="agent-os-runtime@${PROJECT}.iam.gserviceaccount.com"
MODEL="${GEMINI_CORE_MODEL:-gemini-3.6-flash}"
AR_REPO="agent-os"
BUCKET="${ARTIFACT_BUCKET:-${PROJECT}-artifacts}"
PUBSUB_TOPIC="agent-os-workflow-events"
PUBSUB_SUB="agent-os-workflow-worker"
SECRETS=(
  agent-os-google-oauth-client-secret
  agent-os-google-oauth-refresh-token
  agent-os-github-token
)

if [[ -t 1 ]]; then
  R=$'\e[31m'; G=$'\e[32m'; Y=$'\e[33m'; B=$'\e[34m'; DIM=$'\e[2m'; BOLD=$'\e[1m'; X=$'\e[0m'
else
  R=""; G=""; Y=""; B=""; DIM=""; BOLD=""; X=""
fi

PASSES=0; FAILS=0; WARNS=0
FAILED_ITEMS=()

pass()  { printf '  %s[ PASS ]%s %s\n' "$G" "$X" "$1"; PASSES=$((PASSES + 1)); }
fail()  { printf '  %s[ FAIL ]%s %s\n' "$R" "$X" "$1"; FAILS=$((FAILS + 1)); FAILED_ITEMS+=("$1${2:+ -> $2}"); }
warn()  { printf '  %s[ WARN ]%s %s\n' "$Y" "$X" "$1"; WARNS=$((WARNS + 1)); }
note()  { printf '  %s[ NOTE ]%s %s\n' "$B" "$X" "$1"; }
head2() { printf '\n%s%s%s\n' "$BOLD" "$1" "$X"; }
hint()  { printf '           %s%s%s\n' "$DIM" "$1" "$X"; }

printf '%s' "$BOLD"
cat <<BANNER
==========================================================
 Agent OS - deployment access verification
==========================================================
BANNER
printf '%s' "$X"

# ---------------------------------------------------------------- preflight --

head2 "0. Preflight"

for tool in gcloud curl jq; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    fail "$tool is not installed" "Cloud Shell ships all three; are you in Cloud Shell?"
    printf '\n%sCannot continue without %s.%s\n' "$R" "$tool" "$X"
    exit 1
  fi
done
pass "gcloud, curl and jq are available"

ACCOUNT="$(gcloud config get-value account 2>/dev/null)"
if [[ -z "$ACCOUNT" || "$ACCOUNT" == "(unset)" ]]; then
  fail "No authenticated account" "run: gcloud auth login"
  exit 1
fi
pass "Authenticated as ${ACCOUNT}"

TOKEN="$(gcloud auth print-access-token 2>/dev/null)"
if [[ -z "$TOKEN" ]]; then
  fail "Could not mint an access token" "run: gcloud auth login"
  exit 1
fi

CURRENT_PROJECT="$(gcloud config get-value project 2>/dev/null)"
if [[ "$CURRENT_PROJECT" != "$PROJECT" ]]; then
  warn "gcloud project is '${CURRENT_PROJECT}', checking '${PROJECT}' instead"
  hint "to change it: gcloud config set project ${PROJECT}"
else
  pass "Project is ${PROJECT}"
fi

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)' 2>/dev/null)"
if [[ -n "$PROJECT_NUMBER" ]]; then
  pass "Project number is ${PROJECT_NUMBER}"
  hint "PHASE_1_CHECKLIST.md section 2 asks for this - record it"
else
  fail "Cannot read project ${PROJECT}" "wrong project id, or no access at all"
  exit 1
fi

# ------------------------------------------------------------------ billing --

head2 "1. Billing"

BILLING_JSON="$(curl -sS -H "Authorization: Bearer ${TOKEN}" \
  "https://cloudbilling.googleapis.com/v1/projects/${PROJECT}/billingInfo" 2>/dev/null)"
BILLING_ENABLED="$(jq -r '.billingEnabled // empty' <<<"$BILLING_JSON" 2>/dev/null)"
BILLING_ACCOUNT="$(jq -r '.billingAccountName // empty' <<<"$BILLING_JSON" 2>/dev/null)"

if [[ "$BILLING_ENABLED" == "true" ]]; then
  pass "Billing is linked and enabled (${BILLING_ACCOUNT})"
elif [[ "$BILLING_ENABLED" == "false" ]]; then
  fail "Billing is NOT enabled on ${PROJECT}" "OWNER_SETUP.md section 1"
  hint "nothing else will work until the owner links the credited account"
else
  warn "Cannot read billing status - you may lack billing.resourceAssociations.list"
  hint "not a blocker for you; ask the owner to confirm OWNER_SETUP.md section 1"
fi

# --------------------------------------------------------------------- apis --

head2 "2. Enabled APIs"

REQUIRED_APIS=(
  aiplatform.googleapis.com
  run.googleapis.com
  firestore.googleapis.com
  storage.googleapis.com
  secretmanager.googleapis.com
  pubsub.googleapis.com
  cloudbuild.googleapis.com
  artifactregistry.googleapis.com
  logging.googleapis.com
  monitoring.googleapis.com
  cloudtrace.googleapis.com
  iamcredentials.googleapis.com
)
OPTIONAL_APIS=(
  modelarmor.googleapis.com
  calendar-json.googleapis.com
)

ENABLED="$(gcloud services list --enabled --project="$PROJECT" \
  --format='value(config.name)' 2>/dev/null)"

if [[ -z "$ENABLED" ]]; then
  warn "Could not list enabled services - missing serviceusage.services.list"
  hint "OWNER_SETUP.md section 6 grants roles/serviceusage.serviceUsageAdmin"
else
  for api in "${REQUIRED_APIS[@]}"; do
    if grep -qx "$api" <<<"$ENABLED"; then
      pass "$api"
    else
      fail "$api is not enabled" "OWNER_SETUP.md section 3"
    fi
  done
  for api in "${OPTIONAL_APIS[@]}"; do
    if grep -qx "$api" <<<"$ENABLED"; then
      pass "$api ${DIM}(optional)${X}"
    else
      warn "$api is not enabled (optional - P1 feature)"
    fi
  done
fi

# -------------------------------------------------------------- permissions --

head2 "3. Your project permissions"

# Each row: role id | what it unlocks | comma-separated permissions
CHECKS=(
  "roles/run.developer|Deploy and update Cloud Run services|run.services.create,run.services.update,run.services.get,run.services.list,run.revisions.get"
  "roles/aiplatform.user|Call Gemini on Vertex AI|aiplatform.endpoints.predict,aiplatform.models.list"
  "roles/serviceusage.serviceUsageAdmin|Enable Google Cloud APIs yourself|serviceusage.services.enable,serviceusage.services.list"
  "roles/artifactregistry.writer|Push container images|artifactregistry.repositories.get,artifactregistry.repositories.uploadArtifacts,artifactregistry.dockerimages.list"
  "roles/cloudbuild.builds.editor|Build the image from source|cloudbuild.builds.create,cloudbuild.builds.get"
  "roles/datastore.user|Read and write Firestore workflow/audit data|datastore.databases.get,datastore.entities.create,datastore.entities.get"
  "roles/storage.objectAdmin|Read and write artifacts in Cloud Storage|storage.buckets.get,storage.objects.create,storage.objects.get,storage.objects.list"
  "roles/secretmanager.viewer|Confirm secrets exist (names only)|secretmanager.secrets.get,secretmanager.secrets.list"
  "roles/logging.viewer + cloudtrace|Write and read logs and traces|logging.logEntries.create,logging.logEntries.list,cloudtrace.traces.patch"
)

# Permissions that SHOULD be absent. Presence is a least-privilege finding,
# not a failure of this runbook.
LEAST_PRIV=(
  "secretmanager.versions.access|Read secret VALUES|You only need to know secrets exist. The runtime service account reads the values."
  "resourcemanager.projects.setIamPolicy|Change project IAM|Expected to be absent - this is exactly why the owner runs OWNER_SETUP.md."
)

ALL_PERMS=()
for row in "${CHECKS[@]}"; do
  IFS='|' read -r _role _desc perms <<<"$row"
  IFS=',' read -ra parr <<<"$perms"
  ALL_PERMS+=("${parr[@]}")
done
for row in "${LEAST_PRIV[@]}"; do
  IFS='|' read -r perm _rest <<<"$row"
  ALL_PERMS+=("$perm")
done

json_array() {
  local out="" p
  for p in "$@"; do out+="\"${p}\","; done
  printf '[%s]' "${out%,}"
}

PERM_RESPONSE="$(curl -sS -X POST \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"permissions\": $(json_array "${ALL_PERMS[@]}")}" \
  "https://cloudresourcemanager.googleapis.com/v3/projects/${PROJECT}:testIamPermissions" \
  2>/dev/null)"

# Distinguish "the call failed" from "you hold nothing". Without this guard a
# failed request would render as ~9 confident false failures and send the owner
# chasing grants that are already in place.
PERM_ERROR="$(jq -r '.error.message // empty' <<<"$PERM_RESPONSE" 2>/dev/null)"
PERM_QUERY_OK=1

if [[ -n "$PERM_ERROR" ]]; then
  PERM_QUERY_OK=0
  fail "Could not query your permissions" "cloudresourcemanager.googleapis.com may be disabled"
  hint "API said: $(head -c 200 <<<"$PERM_ERROR")"
elif ! jq -e 'has("permissions")' <<<"$PERM_RESPONSE" >/dev/null 2>&1; then
  PERM_QUERY_OK=0
  fail "Unreadable response from testIamPermissions" "cannot assess your permissions"
  hint "raw: $(head -c 200 <<<"$PERM_RESPONSE")"
fi

GRANTED="$(jq -r '.permissions[]?' <<<"$PERM_RESPONSE" 2>/dev/null)"
has_perm() { grep -qx "$1" <<<"$GRANTED"; }

if [[ $PERM_QUERY_OK -eq 0 ]]; then
  warn "Skipping the permission and least-privilege checks"
  hint "an empty result here means 'unknown', not 'denied' - do not act on it"
else
  for row in "${CHECKS[@]}"; do
    IFS='|' read -r role desc perms <<<"$row"
    IFS=',' read -ra parr <<<"$perms"
    missing=()
    for p in "${parr[@]}"; do
      has_perm "$p" || missing+=("$p")
    done
    if [[ ${#missing[@]} -eq 0 ]]; then
      pass "${desc} ${DIM}(${role})${X}"
    else
      fail "${desc} ${DIM}(${role})${X}" "OWNER_SETUP.md section 6"
      hint "missing: ${missing[*]}"
    fi
  done

  head2 "4. Least-privilege checks"

  for row in "${LEAST_PRIV[@]}"; do
    IFS='|' read -r perm label why <<<"$row"
    if has_perm "$perm"; then
      note "You DO hold ${perm} - ${label}"
      hint "$why"
    else
      pass "Correctly absent: ${perm} ${DIM}(${label})${X}"
    fi
  done
fi

# -------------------------------------------------- runtime service account --

head2 "5. Runtime service account"

SA_JSON="$(gcloud iam service-accounts describe "$RUNTIME_SA" \
  --project="$PROJECT" --format=json 2>/dev/null)"

if [[ -z "$SA_JSON" ]]; then
  fail "${RUNTIME_SA} does not exist or is not visible" "OWNER_SETUP.md section 4"
else
  if [[ "$(jq -r '.disabled // false' <<<"$SA_JSON")" == "true" ]]; then
    fail "${RUNTIME_SA} exists but is DISABLED" "re-enable it in the Console"
  else
    pass "${RUNTIME_SA} exists and is enabled"
  fi

  SA_RESPONSE="$(curl -sS -X POST \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{"permissions":["iam.serviceAccounts.actAs","iam.serviceAccounts.get"]}' \
    "https://iam.googleapis.com/v1/projects/${PROJECT}/serviceAccounts/${RUNTIME_SA}:testIamPermissions" \
    2>/dev/null)"
  SA_ERROR="$(jq -r '.error.message // empty' <<<"$SA_RESPONSE" 2>/dev/null)"
  SA_PERMS="$(jq -r '.permissions[]?' <<<"$SA_RESPONSE" 2>/dev/null)"

  if [[ -n "$SA_ERROR" ]]; then
    fail "Could not check actAs on ${RUNTIME_SA}" "treat as unknown, not denied"
    hint "API said: $(head -c 200 <<<"$SA_ERROR")"
  elif grep -qx "iam.serviceAccounts.actAs" <<<"$SA_PERMS"; then
    pass "You can actAs the runtime account ${DIM}(roles/iam.serviceAccountUser)${X}"
  else
    fail "You CANNOT actAs ${RUNTIME_SA}" "OWNER_SETUP.md section 7"
    hint "Cloud Run deploy will fail with PERMISSION_DENIED: iam.serviceaccounts.actAs"
    hint "the grant must be on the service account's own Permissions tab, not project IAM"
  fi

  KEY_COUNT="$(gcloud iam service-accounts keys list --iam-account="$RUNTIME_SA" \
    --project="$PROJECT" --managed-by=user --format='value(name)' 2>/dev/null | grep -c . || true)"
  if [[ "${KEY_COUNT:-0}" -eq 0 ]]; then
    pass "No user-managed keys on the runtime account ${DIM}(AGENTS.md no-keys rule)${X}"
  else
    fail "${KEY_COUNT} user-managed key(s) exist on ${RUNTIME_SA}" "AGENTS.md forbids service-account keys"
    hint "delete them and rely on the attached managed identity instead"
  fi
fi

# ---------------------------------------------------------------- resources --

head2 "6. Resources"

if gcloud artifacts repositories describe "$AR_REPO" \
     --location="$REGION" --project="$PROJECT" >/dev/null 2>&1; then
  pass "Artifact Registry repo '${AR_REPO}' exists in ${REGION}"
else
  fail "Artifact Registry repo '${AR_REPO}' missing in ${REGION}" "OWNER_SETUP.md section 8"
fi

FS_JSON="$(gcloud firestore databases describe --database='(default)' \
  --project="$PROJECT" --format=json 2>/dev/null)"
if [[ -z "$FS_JSON" ]]; then
  fail "Firestore '(default)' database not found" "OWNER_SETUP.md section 9"
else
  FS_LOC="$(jq -r '.locationId // "?"' <<<"$FS_JSON")"
  FS_TYPE="$(jq -r '.type // "?"' <<<"$FS_JSON")"
  if [[ "$FS_LOC" == "$REGION" ]]; then
    pass "Firestore '(default)' is in ${FS_LOC}"
  else
    fail "Firestore is in '${FS_LOC}', expected '${REGION}'" "location is IMMUTABLE"
    hint "recreate the database now, before any data exists"
  fi
  if [[ "$FS_TYPE" == "FIRESTORE_NATIVE" ]]; then
    pass "Firestore is in Native mode"
  else
    fail "Firestore mode is '${FS_TYPE}', expected FIRESTORE_NATIVE" "mode is IMMUTABLE"
  fi
fi

if gcloud storage buckets describe "gs://${BUCKET}" --project="$PROJECT" >/dev/null 2>&1; then
  pass "Bucket gs://${BUCKET} exists"
  if [[ -z "${ARTIFACT_BUCKET:-}" ]]; then
    hint "set ARTIFACT_BUCKET=${BUCKET} in your .env - it is currently empty"
  fi
else
  fail "Bucket gs://${BUCKET} not found" "OWNER_SETUP.md section 10"
  hint "if the owner chose a different name, re-run with ARTIFACT_BUCKET=<name>"
fi

if gcloud pubsub topics describe "$PUBSUB_TOPIC" --project="$PROJECT" >/dev/null 2>&1; then
  pass "Pub/Sub topic '${PUBSUB_TOPIC}' exists"
else
  fail "Pub/Sub topic '${PUBSUB_TOPIC}' missing" "OWNER_SETUP.md section 11"
fi

if gcloud pubsub subscriptions describe "$PUBSUB_SUB" --project="$PROJECT" >/dev/null 2>&1; then
  pass "Pub/Sub subscription '${PUBSUB_SUB}' exists"
else
  fail "Pub/Sub subscription '${PUBSUB_SUB}' missing" "OWNER_SETUP.md section 11"
fi

head2 "7. Secret Manager (names only, never values)"

for s in "${SECRETS[@]}"; do
  if gcloud secrets describe "$s" --project="$PROJECT" >/dev/null 2>&1; then
    pass "Secret '${s}' exists"
  else
    fail "Secret '${s}' missing" "OWNER_SETUP.md section 13"
  fi
done

# ------------------------------------------------------------ vertex ai e2e --

head2 "8. Live Vertex AI check"

hint "countTokens is free and proves billing + API + IAM together"

VERTEX_RESPONSE="$(curl -sS -w $'\n%{http_code}' -X POST \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"contents":[{"role":"user","parts":[{"text":"ping"}]}]}' \
  "https://${REGION}-aiplatform.googleapis.com/v1/projects/${PROJECT}/locations/${REGION}/publishers/google/models/${MODEL}:countTokens" \
  2>/dev/null)"

VERTEX_CODE="$(tail -n1 <<<"$VERTEX_RESPONSE")"
VERTEX_BODY="$(sed '$d' <<<"$VERTEX_RESPONSE")"

case "$VERTEX_CODE" in
  200)
    TOKENS="$(jq -r '.totalTokens // "?"' <<<"$VERTEX_BODY" 2>/dev/null)"
    pass "Vertex AI reachable: ${MODEL} in ${REGION} counted ${TOKENS} tokens"
    ;;
  403)
    fail "Vertex AI returned 403 for ${MODEL}" "OWNER_SETUP.md sections 3 and 6"
    hint "needs aiplatform.googleapis.com enabled AND roles/aiplatform.user"
    hint "$(jq -r '.error.message // empty' <<<"$VERTEX_BODY" 2>/dev/null | head -c 200)"
    ;;
  404)
    fail "Model '${MODEL}' not found in ${REGION}" "check GEMINI_CORE_MODEL"
    hint "the model id in .env.example may not be available in this region yet"
    hint "list what is available, then update .env and app/settings.py to match"
    ;;
  *)
    fail "Vertex AI check failed with HTTP ${VERTEX_CODE}" "see message below"
    hint "$(jq -r '.error.message // empty' <<<"$VERTEX_BODY" 2>/dev/null | head -c 200)"
    ;;
esac

# ------------------------------------------------------------------ summary --

head2 "Summary"

printf '  %s%d passed%s   %s%d failed%s   %s%d warnings%s\n' \
  "$G" "$PASSES" "$X" "$R" "$FAILS" "$X" "$Y" "$WARNS" "$X"

if [[ $FAILS -gt 0 ]]; then
  printf '\n  %sBlocking items:%s\n' "$BOLD" "$X"
  for item in "${FAILED_ITEMS[@]}"; do
    printf '   - %s\n' "$item"
  done
  printf '\n  Send this output to the project owner. Each item names the\n'
  printf '  OWNER_SETUP.md section that fixes it.\n\n'
  exit 1
fi

printf '\n  %sProject %s is ready for the first deployment.%s\n\n' "$G" "$PROJECT" "$X"
exit 0
