// On Scene bot timer (Cloudflare Worker).
// GitHub's own schedule skips most runs, so this asks GitHub to run the bot every 5 minutes.
// It holds one secret, GITHUB_TOKEN: a fine-grained token limited to the on-scene repo
// with "Actions: Read and write". The token never appears in this file.

const WORKFLOW = "https://api.github.com/repos/rebekahambrose/on-scene/actions/workflows/collect.yml/dispatches";

async function trigger(env) {
  const res = await fetch(WORKFLOW, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "on-scene-timer",
      "X-GitHub-Api-Version": "2022-11-28",
    },
    body: JSON.stringify({ ref: "main" }),
  });
  return res.status; // 204 means GitHub accepted it
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(trigger(env));
  },
  // Visiting the worker's address does nothing but say it exists, so nobody can set off extra runs.
  async fetch() {
    return new Response("On Scene timer. Runs happen on its schedule only.", { headers: { "content-type": "text/plain" } });
  },
};
