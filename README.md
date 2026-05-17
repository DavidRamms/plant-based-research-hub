# Plant-Based Research Hub

A daily-updating static site that tracks peer-reviewed research on plant-based diets. Studies are fetched automatically from PubMed, stored in SQLite, summarized by an AI model (Llama 3.3 70B via Groq), and published as a static site on GitHub Pages.

## What it does

- Fetches studies from [PubMed](https://pubmed.ncbi.nlm.nih.gov/) across 11 research topics (cardiovascular health, cancer risk, diabetes, bone density, gut microbiome, protein/muscle, cognition, longevity, nutrient deficiencies, environmental impact, Mediterranean diet)
- Classifies studies by evidence quality (meta-analyses → RCTs → cohort → cross-sectional → case reports)
- Generates structured AI narrative summaries: consensus, evidence evolution, agreements, conflicts, limitations, and open questions
- Builds a fully static site with per-topic pages, a searchable study database, and a methodology/glossary page
- Updates automatically every day at 06:00 UTC via GitHub Actions

## Running manually

### First run (bootstrap — fetches last 5 years)

```bash
pip install -r requirements.txt
export GROQ_API_KEY="your_groq_api_key_here"
python scripts/run_all.py --bootstrap
```

### Subsequent runs (fetches last year only)

```bash
python scripts/run_all.py
```

### Force regenerate all summaries

```bash
python scripts/run_all.py --force-resynthesis
```

## GitHub Pages setup

1. Push this repository to GitHub.
2. Add your Groq API key as a repository secret named `GROQ_API_KEY`.
3. In repository Settings → Pages, set the source to the `docs/` folder on your main branch.
4. The workflow will run daily and push updated HTML to `docs/`.

## Project structure

```
plant-research/
├── .github/workflows/daily-update.yml   # GitHub Actions workflow
├── scripts/
│   ├── config.py           # Topics, quality tiers, constants
│   ├── database.py         # SQLite helpers
│   ├── fetch_studies.py    # PubMed E-utilities fetcher
│   ├── generate_summaries.py  # Groq AI summary generation
│   ├── build_site.py       # Static HTML builder (Jinja2)
│   └── run_all.py          # Pipeline entry point
├── docs/                   # GitHub Pages output
│   ├── assets/
│   │   ├── style.css
│   │   └── main.js
│   └── .nojekyll
├── data/                   # SQLite database (gitignored or committed)
├── requirements.txt
└── README.md
```

## Notes

- No PubMed API key is required (the free tier allows ~3 requests/second; the pipeline adds a 0.4s delay between requests).
- Summaries are regenerated on any day new studies are found, plus every Sunday for a full refresh.
- The site does not provide medical advice. All content is for informational purposes only.
