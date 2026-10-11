
"""Configuration module for RSS news sources in EcoPulse.

This file centralizes all public RSS feeds collected by the system.
You can easily add, edit, or disable feeds here without modifying
the collector logic.
"""

# Configurable list of trusted public RSS feeds
RSS_SOURCES = [

    # --------------------------------------------------
    # EXISTING ENVIRONMENT SOURCES
    # --------------------------------------------------

    {
        "name": "The Hindu - Energy & Environment",
        "url": "https://www.thehindu.com/sci-tech/energy-and-environment/feeder/default.rss",
        "location": "India",
        "type": "environment",
        "enabled": True,
    },

    {
        "name": "BBC News - Science & Environment",
        "url": "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
        "location": "Global",
        "type": "environment",
        "enabled": True,
    },

    {
        "name": "UN News - Climate Change",
        "url": "https://news.un.org/feed/subscribe/en/news/topic/climate-change/feed/rss.xml",
        "location": "Global",
        "type": "climate",
        "enabled": True,
    },

    # --------------------------------------------------
    # CHENNAI / TAMIL NADU LOCAL SOURCES
    # --------------------------------------------------

    {
        "name": "The Hindu - Chennai",
        "url": "https://www.thehindu.com/news/cities/chennai/feeder/default.rss",
        "location": "Chennai",
        "type": "local",
        "enabled": True,
    },

    {
        "name": "The Hindu - Tamil Nadu",
        "url": "https://www.thehindu.com/news/national/tamil-nadu/feeder/default.rss",
        "location": "Tamil Nadu",
        "type": "local",
        "enabled": True,
    },

    # --------------------------------------------------
    # PUBLIC TRANSPORT
    # --------------------------------------------------

    {
        "name": "ET Infra - Urban Transportation",
        "url": "https://infra.economictimes.indiatimes.com/rss/urban-transportation",
        "location": "India",
        "type": "transport",
        "enabled": True,
    },

    # --------------------------------------------------
    # ADDITIONAL INDIA & CHENNAI CIVIC / ECO SOURCES
    # --------------------------------------------------

    {
        "name": "Times of India - Chennai",
        "url": "https://timesofindia.indiatimes.com/rssfeeds/2950623.cms",
        "location": "Chennai",
        "type": "local",
        "enabled": True,
    },

    {
        "name": "Times of India - Environment",
        "url": "https://timesofindia.indiatimes.com/rssfeeds/2647163.cms",
        "location": "India",
        "type": "environment",
        "enabled": True,
    },

    {
        "name": "Indian Express - Chennai",
        "url": "https://indianexpress.com/section/cities/chennai/feed/",
        "location": "Chennai",
        "type": "local",
        "enabled": True,
    },

    # --------------------------------------------------
    # CAMPUS SUSTAINABILITY
    # --------------------------------------------------

    {
        "name": "Sustainable Cornell - Campus Sustainability",
        "url": "https://sustainable.cornell.edu/news/rss.xml",
        "location": "Global",
        "type": "campus",
        "enabled": True,
    },

]


def get_active_sources():
    """Return only the RSS sources marked as enabled.

    Returns:
        list: Filtered list of active source dictionaries.
    """
    return [source for source in RSS_SOURCES if source.get("enabled", True)]