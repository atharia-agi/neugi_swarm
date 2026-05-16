# SEO Strategy — NEUGI Swarm

## Meta Tags

Every HTML page includes the following meta tags in `<head>`:

### Open Graph (Social Sharing)

```html
<meta property="og:title" content="NEUGI Swarm — Autonomous Multi-Agent Framework" />
<meta property="og:description" content="Production-grade autonomous multi-agent framework with 29 subsystems, 120+ modules, memory consolidation, and proactive behavior." />
<meta property="og:image" content="https://neugi.com/assets/og-image.png" />
<meta property="og:url" content="https://neugi.com/" />
<meta property="og:type" content="website" />
```

### Twitter Cards

```html
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="NEUGI Swarm" />
<meta name="twitter:description" content="Production-grade autonomous multi-agent framework." />
<meta name="twitter:image" content="https://neugi.com/assets/og-image.png" />
```

### Canonical URL

```html
<link rel="canonical" href="https://neugi.com/" />
```

### robots.txt + Sitemap

- **robots.txt** — `https://neugi.com/robots.txt` — allows all crawlers, points to sitemap.
- **Sitemap** — `https://neugi.com/sitemap.xml` — lists all public pages with priority and change frequency.

### Schema.org Markup (SoftwareApplication)

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "NEUGI Swarm",
  "applicationCategory": "DeveloperApplication",
  "operatingSystem": "Cross-platform",
  "description": "Production-grade autonomous multi-agent framework with 29 subsystems, 120+ modules, memory consolidation, and proactive behavior.",
  "url": "https://neugi.com/",
  "author": {
    "@type": "Organization",
    "name": "NEUGI"
  }
}
</script>
```

## Files

| File | Location | Purpose |
|------|----------|---------|
| `sitemap.xml` | `/sitemap.xml` | Search engine crawling guide |
| `robots.txt` | `/robots.txt` | Crawler permissions + sitemap link |

## Notes

- All OG/Twitter images should be 1200×630 px.
- Update `lastmod` in sitemap.xml on each deploy.
- Schema.org `SoftwareApplication` type improves rich search result eligibility.
