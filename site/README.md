# LearnCad site

Static landing page and free course catalog. No build step, framework, or
external CDNs.

## Preview

From the repository root:

```bash
python3 -m http.server 8000 --directory site
```

Open <http://127.0.0.1:8000/>.

## Pages

- `index.html` - landing page, features, install steps, and FAQ.
- `courses/index.html` - free `.learncad` catalog and download page.
- `courses/catalog.json` - generated catalog. Do not edit by hand.
- `courses/packages/` - generated `.learncad` packages. Do not edit by hand.
- `styles.css` - shared design.
- `script.js` - mobile nav and current year.
- `robots.txt`, `sitemap.xml` - SEO files.
- `assets/` - logo, favicon, social image.
- `downloads/` - installer artifacts.

## Before deploying

Replace the placeholder domain in every file. Search for:

```text
learncad.example.com
```

Update:

- `index.html` canonical, Open Graph, Twitter, and JSON-LD URLs.
- `courses/index.html` canonical and Open Graph URLs.
- `robots.txt` sitemap URL.
- `sitemap.xml` loc entries.

The download buttons use local files. For production, upload
`site/downloads/` or point them at GitHub Releases.

## SEO checklist

- Submit `sitemap.xml` in Google Search Console and Bing Webmaster Tools.
- Confirm the canonical URLs match the live domain.
- Keep the pages static and fast. No external fonts or trackers.
- Keep the site mobile-friendly.
- Add real screenshots and a 60-90 second demo video.
- Target practical searches: "learn CAD", "CAD for beginners",
  "CAD constraints explained", "CAD pad failed", and "CAD for 3D printing".
- Share useful answers on CAD communities, r/3Dprinting, Hacker News, and
  YouTube. Link the site only when it answers the question.

## Demo video

Record a 60-90 second screen capture:

1. 0-10s: a beginner is stuck on an under-constrained sketch.
2. 10-30s: LearnCad explains the missing constraint and preselects the
   endpoints.
3. 30-50s: Guide me opens the Pad or Hole dialog.
4. 50-70s: a valid solid, export, and the result.

Save it as `site/assets/demo.mp4` and a poster as
`site/assets/demo-poster.png`.

## Rebuilding the course catalog

Course sources live in `courses/`, one folder per course with a
`manifest.json`. After adding or editing a course:

```bash
python3 tools/course_tool.py build
python3 tools/course_tool.py check site/courses/catalog.json
```

`build` packs every source folder, removes stale packages, and regenerates
`site/courses/catalog.json`. Commit the source folder and the generated
packages and catalog together.

## Rebuilding downloads

After a new Windows installer build:

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\build_installer.ps1
```

Then copy the new files into `site/downloads/` and update the version, size,
and SHA256 values in `index.html` and `courses/index.html`.

## Deployment

Any static host works:

- Cloudflare Pages
- Netlify
- Vercel
- GitHub Pages
- A plain nginx/Apache folder

Set the site root to `site/`. No server-side code is required.
