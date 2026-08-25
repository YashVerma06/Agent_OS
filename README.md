# Agent OS — Google Cloud Handoff

This folder contains the Google Cloud setup guide for the Agent OS hackathon MVP.

## For the Google Cloud administrator

1. Open `Agent_OS_Google_Cloud_Admin_Handoff.docx`.
2. Complete the IAM, API, service-identity, resource, billing-alert, and Calendar OAuth steps.
3. Fill out the **Safe Return Package** in Section 10 and send only that completed section back to the Agent OS team.

## Important security rule

Do **not** send API keys, service-account JSON files, private keys, OAuth client secrets, refresh tokens, billing identifiers, coupon codes, GitHub tokens, or OpenAI keys.

Google Cloud model access must use IAM and Application Default Credentials locally, and managed service identities in production. Third-party secrets must be stored directly in Google Secret Manager.

## Project details

- Project: `agent-os-506306`
- Region: `us-central1`
- Operator: `arpitmishrapy@gmail.com`
- Repository: <https://github.com/arpitmisra/AgentOS>

If a setup step fails, return the exact error message with all secrets and account identifiers redacted.
