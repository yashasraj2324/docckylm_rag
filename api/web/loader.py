import os

from firecrawl import FirecrawlApp
from langchain_core.documents import Document


def get_firecrawl_app():
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        raise ValueError("FIRECRAWL_API_KEY is not set in environment.")
    return FirecrawlApp(api_key=api_key)


def load_url(url: str):
    """Scrapes a single URL and returns it as a Langchain Document."""
    app = get_firecrawl_app()
    result = app.scrape(url)

    # Depending on firecrawl-py version, result might be a dict or a Document object
    if isinstance(result, dict):
        text = result.get("markdown", result.get("content", str(result)))
        meta = result.get("metadata", {})
    else:
        text = getattr(result, "markdown", getattr(result, "content", str(result)))
        meta = getattr(result, "metadata", {})
        # if metadata is an object, convert to dict
        if not isinstance(meta, dict) and hasattr(meta, "model_dump"):
            meta = meta.model_dump()
        elif not isinstance(meta, dict) and hasattr(meta, "__dict__"):
            meta = meta.__dict__

    metadata = {
        "source": url,
        "title": (
            meta.get("title", url)
            if isinstance(meta, dict)
            else getattr(meta, "title", url)
        ),
    }
    return [Document(page_content=text, metadata=metadata)]


def fetch_search_results(query: str):
    """Searches the web and returns a list of parsed result dicts."""
    app = get_firecrawl_app()
    search_result = app.search(query)

    # In firecrawl-py v4.8.x, search_result is a SearchData object with a .web property
    if hasattr(search_result, "web") and search_result.web:
        results_list = search_result.web
    elif isinstance(search_result, list):
        results_list = search_result
    elif isinstance(search_result, dict):
        results_list = search_result.get("data", search_result.get("results", []))
    else:
        results_list = getattr(
            search_result, "data", getattr(search_result, "results", [])
        )

    parsed = []
    for r in results_list:
        if isinstance(r, dict):
            url = r.get("url", "")
            title = r.get("title", "Untitled")
        else:
            url = getattr(r, "url", "")
            title = getattr(r, "title", "Untitled")

        if url:
            parsed.append({"url": url, "title": title})
    # Return top 3 results to avoid overloading the background worker
    return parsed[:3]


def load_search(query: str):
    return []
