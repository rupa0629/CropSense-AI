# Data retention and deletion

CropSense stores the minimum information required for accounts, analysis
history, weather history, chatbot continuity, security tokens and prediction
quality review.

Default retention windows:

- analysis history: 730 days;
- weather history: 365 days;
- chatbot messages: 90 days;
- expired or revoked authentication/reset tokens: removed during every purge.

Configure the windows with `ANALYSIS_RETENTION_DAYS`,
`WEATHER_RETENTION_DAYS`, and `CHAT_RETENTION_DAYS`.

Run `python scripts/purge_expired_data.py` daily from the platform scheduler.
The command logs counts only and never logs message, email, image or location
contents.

`DELETE /auth/me` requires the current password and atomically deletes the
account, settings, tokens, analyses, weather, chat history, feedback and review
queue entries.

Backups may retain deleted data until the encrypted backup retention period
expires. Document that period in the public privacy notice.
