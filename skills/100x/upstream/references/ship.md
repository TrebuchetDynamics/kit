# Stage 7. Ship

Done when there is a preview URL that you tested quickly, or a recorded reason there is none. Production is never part of this stage unless the brief says "deploy to production" in words.

## When to deploy a preview

`deploy.preview` is `auto` by default. Deploy a preview when the project has a deploy setup. `100x init` lists hints such as `vercel.json`, `netlify.toml`, `wrangler.toml`, `firebase.json` or `fly.toml`. `deploy.previewCommand` in config overrides the choice. `ask` and `off` mean skip and say why in the log.

## How

- Use the platform's preview mode and never its production flag. Vercel `vercel` without `--prod`. Netlify `netlify deploy` without `--prod`. Cloudflare Pages `wrangler pages deploy` to a non production branch. Firebase `firebase hosting:channel:deploy`.
- Use the login that already exists on the machine. When the CLI asks to sign in, stop, log "no preview, not signed in to <platform>", and move on. Do not create accounts and do not paste tokens anywhere.
- Capture the URL, then `100x shots <preview url> --label ship --matrix phone`. A preview that does not render is a finding to fix before finishing.
- Record the URL with `100x run set ship '{"preview":"<url>","note":""}'`. When there is no preview, `100x run set ship '{"note":"<why there is none>"}'`.

## When the brief says production

Do the preview first and test it quickly. Then deploy to production with the platform's own command, test it quickly again, and record both URLs under `ship`. Log a `ship` row naming the sentence in the brief that asked for it.

## Never

Never push to a remote, open a pull request, or change DNS. Never deploy a project that holds secrets in the repo. Tell the owner instead.
