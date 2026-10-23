# Setting up the bot timer

GitHub's built-in schedule skips most runs. This free Cloudflare timer asks GitHub to
run the bot every 5 minutes. About 10 minutes, all in the browser.

## 1. Make a GitHub token (only you can do this)

1. Go to https://github.com/settings/personal-access-tokens/new
2. **Token name:** `on-scene-timer`
3. **Expiration:** 1 year (put a reminder on your calendar to renew it)
4. **Repository access:** *Only select repositories* → pick **on-scene**
5. **Permissions → Repository permissions → Actions:** *Read and write*. Leave everything else as is.
6. Click **Generate token** and copy it. You only see it once. Don't paste it anywhere except step 3 below.

## 2. Make the Cloudflare timer

1. Sign up free at https://dash.cloudflare.com/sign-up
2. In the left menu: **Compute (Workers)** → **Workers & Pages** → **Create** → **Create Worker** (start from "Hello World").
3. Name it `on-scene-timer` and click **Deploy**.
4. Click **Edit code**, delete everything in the editor, paste in the contents of `timer/worker.js`, and click **Deploy**.

## 3. Give it the token

1. Go back to the worker → **Settings** → **Variables and Secrets** → **Add**.
2. **Type:** Secret. **Name:** `GITHUB_TOKEN`. **Value:** the token from step 1.
3. Click **Deploy**.

## 4. Turn on the schedule

1. Worker → **Settings** → **Trigger Events** → **Add** → **Cron Triggers**.
2. Choose **Custom** and enter: `*/5 * * * *`
3. Click **Add**.

## 5. Check it works

Within 10 minutes, https://github.com/rebekahambrose/on-scene/actions should show new
runs labeled **workflow_dispatch** every 5 minutes, and the map's "Updated" time should
stay under 15 minutes.
