# FireScrapling: Product Improvement Roadmap 🚀

This roadmap outlines the key architectural and feature-level improvements required to reach parity with top-tier extraction platforms like Firecrawl.

## 🏁 Phase 1: High-Performance Infrastructure (Short Term)
- [ ] **Distributed Worker Nodes**: Implement a Celery/Redis based task queue to handle thousands of concurrent `/crawl` and `/scrape` requests across multiple nodes.
- [ ] **Smart Proxy Rotation**: Integrate a provider like Bright Data or Oxylabs with smart country-level routing and automatic failure retry logic.
- [ ] **Caching Layer**: Implement a 24-hour cache for `/scrape` results to reduce redundant extraction costs and improve response times.
- [ ] **Browser Management (Playwright)**: Full migration to a managed Playwright/Puppeteer fleet for complex SPA (Single Page Application) rendering and screenshotting.

## 🤖 Phase 2: AI & Extraction Intelligence (Medium Term)
- [ ] **Visual Extraction**: Multi-modal extraction support using GPT-4o-vision to "see" the page and extract data based on visual layout.
- [ ] **Dynamic Action Record & Playback**: A Chrome extension for users to record interaction scripts (click, fill, hover) and execute them via the `/scrape` endpoint.
- [ ] **Automatic Schema Inference**: An AI-powered utility that detects the page type (Product, Article, Person) and automatically generates a structured JSON schema.
- [ ] **Markdown Refinement**: Improved post-processing to strip boilerplate and handle nested tables/complex layouts more accurately.

## 🕸️ Phase 3: Advanced Crawling & Mapping (Long Term)
- [ ] **Depth-First vs. Breadth-First Crawling**: Advanced crawl orchestration to prioritize specific subdirectories or patterns.
- [ ] **Sitemap Integration**: Automatically fetch and parse `sitemap.xml` for faster and more accurate domain mapping.
- [ ] **Incremental Crawling**: Only scrape pages that have changed since the last crawl job based on ETag or Last-Modified headers.
- [ ] **Full-Text Search Indexing**: Store crawl results in a vector database (like Pinecone) to provide an instant RAG-ready search endpoint.

## 💼 Phase 4: Enterprise & Ecosystem (Scale)
- [ ] **Robust Webhook Framework**: Comprehensive event system for `crawl.completed`, `crawl.failed`, and `page.scraped` with retry headers and signature verification.
- [ ] **Team Workspaces**: Support for multiple users within a single billing account, with role-based access control (RBAC).
- [ ] **Official SDKs**: Release of official libraries for Python, Node.js, Go, and Rust.
- [ ] **Rate Limiting & Quotas**: Sophisticated per-tier and per-key rate limiting infrastructure.

---

## 🏗️ Technical Parity Checklist
| Feature | Current (v1.8.0) | Target (Firecrawl Level) | Status |
| :--- | :---: | :---: | :---: |
| **JS Rendering** | Simulated / Basic | Full Playwright/Stealth | 🟡 In Progress |
| **Proxying** | Single Exit | Residential / Mobile Rotated | 🔴 Planned |
| **Crawl Speed** | Serial | Highly Parallel (Workers) | 🔴 Planned |
| **AI Extraction** | Basic Schema | Multi-modal / Auto-inference | 🟡 In Progress |
| **Webhook Logic** | Placeholder | Signed / Retried / Atomic | 🔴 Planned |
| **API Compliance** | OpenAPI 3.1 | Full REST / SDK Suite | 🟢 Complete |
