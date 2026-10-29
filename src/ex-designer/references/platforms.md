# Platforms: what a takeover can do on each

Version 1 runs the whole flow for sites with code in a repository. Other platforms get steps 0–3 (intake, public
audit, ownership gate, access list) and a row here; the design values stay where the platform keeps them.

| Platform | How to recognise it | Where the design values live | Access route (never a password) | What v1 does |
|---|---|---|---|---|
| Code in a repository (Next.js, Vite, Astro, Vinext, plain HTML) | the repository, `package.json`, the build output's file names | the project's token file (`globals.css`, a theme file, a Tailwind config) | repository collaborator; hosting team member | the whole flow, steps 0–8 |
| Framer, hosted by Framer | `data-framer` attributes, `framerusercontent.com` assets, Framer's server headers | the Framer project's styles and variables | the owner invites the user's Framer account to the project | audit and access list; no change in v1 |
| Framer, exported and self-hosted | Framer markup on another host (often a shared host's server header); no Framer server headers | baked into the exported HTML and CSS; no source | hosting panel invite (for example a shared host's account sharing) | audit and access list; no change in v1. Framer has no official export: the owner's Framer project or a rebuild is its own decision |
| Webflow | `data-wf-site`, `webflow.js`, `website-files.com` assets | Webflow's style panel and variables | workspace or site invite | audit and access list; no change in v1 |
| WordPress | `/wp-content/`, `/wp-json/`, the generator meta tag | the theme (`theme.json`, a child theme's CSS), the customizer, page builders | an administrator or editor account created for the user by the owner | audit and access list; no change in v1 (a child theme with a token file is a later option) |
| Wix / Squarespace | `static.wixstatic.com` / `squarespace` assets and headers | the site editor's theme settings | contributor invite from the owner | audit and access list; no change in v1 |

A rebuild into code makes "continue the design" literally true on a builder site, but it is weeks of migration with
search-ranking risk: a per-site decision for the owner, never the default.
