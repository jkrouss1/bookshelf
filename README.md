# Jared's Bookshelf

A visual library built from the "Jared Krouss Bookshelf" Google Sheet.

- `index.html`: the whole site. It reads the sheet live every time it loads.
- `covers.json`: saved covers and spine colors, refreshed nightly by `.github/workflows/covers.yml`.
- `scripts/build_covers.py`: finds covers on Open Library, with Google Books as a fallback.

## Adding books
Add a row to the sheet. To mark a new favorite, type `Favorite` or `Life Changing` in column F.
The site shows the new book right away. Its cover appears in the browser right away and is saved to `covers.json` that night.

## Hosting on krouss.org (GitHub Pages)
1. Push this folder to a GitHub repo.
2. Go to Settings → Pages → Deploy from branch `main`, folder `/`. Set the custom domain to `books.krouss.org`.
3. At the DNS provider for krouss.org, add a CNAME record from `books` to `<github-username>.github.io`.
4. Go to Actions → "Update book covers" → Run workflow, so the first full set of covers is saved now instead of tonight.

## Wrong cover?
Edit that book's entry in `covers.json`: change `src` to a better image URL and delete `color` so the next run recomputes it. Or set it to `{"none": 9999999999999}` to use the plain typeset jacket.
