"""All settings for Daily Tech Digest: sections, feeds, search queries, filters."""
import os
from urllib.parse import quote

SECTIONS = [
    {
        "slug": "frontier-ai", "name": "Frontier AI", "color": "#7C3AED",
        "blurb": "Model releases, AI launches, research & frontier-lab moves",
        "brief": "New models and updates from OpenAI, Anthropic, Google, Meta, Mistral, DeepSeek; major AI product launches; notable research; big AI company news.",
    },
    {
        "slug": "global-tech", "name": "Global Tech", "color": "#0284C7",
        "blurb": "Big-tech strategy, platforms, chips, regulation & earnings",
        "brief": "Major moves by global tech companies. Tech news that isn't from an AI lab goes here.",
    },
    {
        "slug": "india-startups", "name": "India Startups", "color": "#D97706",
        "blurb": "Funding, launches, layoffs, IPOs & policy in Indian tech",
        "brief": "Funding, launches, layoffs, IPOs and policy in Indian tech and startups.",
    },
    {
        "slug": "product-craft", "name": "Product Craft", "color": "#059669",
        "blurb": "PM frameworks, essays & product launches worth studying",
        "brief": "PM frameworks, essays, growth and strategy lessons, product launches and redesigns worth studying.",
    },
    {
        "slug": "creative-tools", "name": "Creative Tools", "color": "#E11D48",
        "blurb": "Adobe, AI imaging, cameras & how creators are reacting",
        "brief": "Adobe products (Photoshop, Lightroom, Firefly, Premiere, Illustrator, Express), photo-editing tech, AI image generators and editors (Midjourney, Stable Diffusion, Flux), camera and photography tech, and creator reactions. NEVER stories whose subject is an Adobe competitor (Canva, Affinity, Capture One, Figma, Corel, PaintShop, Pixelmator, Luminar/Skylum).",
    },
]
SECTION_BY_SLUG = {s["slug"]: s for s in SECTIONS}

MAX_PER_SECTION = 6
TOP_N = 5


def gnews(q, window="1d"):
    return ("https://news.google.com/rss/search?q="
            + quote(f"{q} when:{window}") + "&hl=en-IN&gl=IN&ceid=IN:en")


# Direct publisher feeds. (url, source name, max age hours)
FEEDS = {
    "frontier-ai": [
        ("https://techcrunch.com/category/artificial-intelligence/feed/", "TechCrunch", 24),
        ("https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "The Verge", 24),
        ("https://www.technologyreview.com/topic/artificial-intelligence/feed/", "MIT Technology Review", 24),
        ("https://hnrss.org/frontpage?points=150", "Hacker News", 24),
    ],
    "global-tech": [
        ("https://techcrunch.com/feed/", "TechCrunch", 24),
        ("https://www.theverge.com/rss/index.xml", "The Verge", 24),
        ("https://feeds.arstechnica.com/arstechnica/index", "Ars Technica", 24),
    ],
    "india-startups": [
        ("https://economictimes.indiatimes.com/tech/startups/rssfeeds/78570540.cms", "Economic Times", 24),
        ("https://economictimes.indiatimes.com/tech/rssfeeds/13357270.cms", "Economic Times", 24),
        ("https://inc42.com/feed/", "Inc42", 24),
        ("https://yourstory.com/feed", "YourStory", 24),
        ("https://www.moneycontrol.com/rss/business.xml", "Moneycontrol", 24),
    ],
    "product-craft": [
        ("https://www.lennysnewsletter.com/feed", "Lenny's Newsletter", 96),
        ("https://www.producthunt.com/feed", "Product Hunt", 24),
    ],
    "creative-tools": [
        ("https://petapixel.com/feed/", "PetaPixel", 24),
        ("https://fstoppers.com/feed", "Fstoppers", 24),
        ("https://www.reddit.com/r/photoshop/top/.rss?t=day", "Reddit r/photoshop", 24),
        ("https://www.reddit.com/r/photography/top/.rss?t=day", "Reddit r/photography", 24),
    ],
}

QUERIES = {
    "frontier-ai": [
        'OpenAI OR Anthropic OR Claude OR "Google Gemini" OR "Meta AI" OR Mistral OR DeepSeek model',
        '"AI model" launch OR release OR "research paper" OR breakthrough',
    ],
    "global-tech": [
        "Apple OR Microsoft OR Amazon OR Google OR Nvidia OR Meta acquisition OR strategy OR launch",
        "tech regulation OR antitrust OR chips OR earnings big tech",
    ],
    "india-startups": [
        "Indian startup funding OR raises OR layoffs OR IPO OR acquisition",
        "India startup policy OR SEBI OR RBI fintech OR quick commerce",
    ],
    "product-craft": [
        "site:review.firstround.com OR site:svpg.com OR site:mindtheproduct.com OR site:reforge.com",
        '"product management" OR "product manager" framework OR strategy OR lessons',
        '"product launch" OR "new feature" OR redesign users growth',
    ],
    "creative-tools": [
        "site:dpreview.com",
        'Photoshop OR Lightroom OR "Adobe Firefly" OR "Adobe MAX"',
        '"Adobe Premiere" OR "Adobe Illustrator" OR "Adobe Express" OR "Generative Fill"',
        'Midjourney OR "Stable Diffusion" OR "AI image" editor OR generator',
        "Adobe creators OR photographers backlash OR controversy OR react",
    ],
}

# Adobe competitors: a story whose subject is one of these is dropped.
COMPETITORS = ["canva", "affinity", "capture one", "figma", "coreldraw", "corel",
               "paintshop", "pixelmator", "luminar", "skylum"]

# AI (Gemini free tier). Empty key => everything uses non-AI fallbacks.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL_SET = bool(os.environ.get("GEMINI_MODEL", "").strip())
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "").strip() or "gemini-flash-lite-latest"

# Email (Gmail SMTP with an App Password). Empty => email skipped.
GMAIL_USER = os.environ.get("GMAIL_USER", "").strip()
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
EMAIL_TO = os.environ.get("EMAIL_TO", "").strip() or GMAIL_USER


DEFAULT_SITE_URL = "https://techdail.vercel.app/"


def site_url():
    explicit = os.environ.get("SITE_URL", "").strip() or DEFAULT_SITE_URL
    if explicit:
        return explicit.rstrip("/") + "/"
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" in repo:
        owner, name = repo.split("/", 1)
        if name.lower() == f"{owner.lower()}.github.io":
            return f"https://{owner.lower()}.github.io/"
        return f"https://{owner.lower()}.github.io/{name}/"
    return "https://example.github.io/daily-tech-digest/"


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_DIR = os.path.join(ROOT, "site")
DATA_DIR = os.path.join(SITE_DIR, "data")
CACHE_DIR = os.path.join(ROOT, "cache")  # article text cache (not published)
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36 DailyTechDigest/1.0")
