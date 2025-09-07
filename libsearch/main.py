from __future__ import annotations

import re
from typing import List, Dict, Any, Optional
from fastmcp import FastMCP

# Import the library search client
from library_searcher import LibSearchClient

# Server name for MCP registry/clients
mcp = FastMCP("Library Search Server", log_level="ERROR")


def _calculate_relevance_score(document: Dict[str, Any], query_terms: List[str]) -> float:
    """Calculate relevance score for a document based on query terms.
    
    Scoring weights:
    - Title Match: 3.0 points per matching term
    - Subject Match: 2.5 points per matching term
    - Author Match: 2.0 points per matching term
    - Description Match: 1.0 point per matching term
    - Availability Bonus: +1.5 points
    - Recent Publication Bonus: +0.5 points (2015+), +0.75 points (2020+)
    """
    score = 0.0

    # Helper function to safely extract text from nested structures
    def extract_text(obj: Any) -> str:
        if isinstance(obj, str):
            return obj.lower()
        elif isinstance(obj, list):
            return ' '.join(str(item) for item in obj).lower()
        elif isinstance(obj, dict):
            return ' '.join(str(value) for value in obj.values()).lower()
        return str(obj).lower() if obj else ""

    # Extract document fields safely
    try:
        pnx = document.get('pnx', {})
        display = pnx.get('display', {})
        addata = pnx.get('addata', {})
        search = pnx.get('search', {})
        facets = pnx.get('facets', {})

        title_text = extract_text(display.get('title', ''))
        author_text = extract_text(display.get('creator', '')) + ' ' + extract_text(addata.get('au', ''))
        subject_text = extract_text(display.get('subject', '')) + ' ' + extract_text(facets.get('topic', ''))
        description_text = extract_text(display.get('description', '')) + ' ' + extract_text(
            search.get('description', ''))

        # Calculate field-based scores
        for term in query_terms:
            if len(term) < 2:  # Skip very short terms
                continue

            term_lower = term.lower()

            # Title matches (highest weight)
            if term_lower in title_text:
                score += 3.0

            # Subject matches
            if term_lower in subject_text:
                score += 2.5

            # Author matches
            if term_lower in author_text:
                score += 2.0

            # Description matches
            if term_lower in description_text:
                score += 1.0

        # Availability bonus
        availability = extract_text(display.get('avail', ''))
        if 'available' in availability or 'online' in availability:
            score += 1.5

        # Publication year bonus
        try:
            year_text = extract_text(display.get('creationdate', '')) or extract_text(addata.get('date', ''))
            year_match = re.search(r'\b(19|20)\d{2}\b', year_text)
            if year_match:
                year = int(year_match.group())
                if year >= 2020:
                    score += 0.75
                elif year >= 2015:
                    score += 0.5
        except (ValueError, TypeError):
            pass

    except Exception:
        # If there's any error in scoring, return a minimal score
        pass

    return score


def _format_search_result(document: Dict[str, Any], rank: Optional[int] = None, score: Optional[float] = None) -> str:
    """Format a single search result for display."""
    try:
        pnx = document.get('pnx', {})
        display = pnx.get('display', {})
        addata = pnx.get('addata', {})
        docId = pnx.get('control').get('recordid')

        # Helper function to clean and format field values
        def clean_field(field: Any) -> str:
            if isinstance(field, list):
                return ', '.join(str(item) for item in field if item)
            return str(field) if field else "N/A"

        title = clean_field(display.get('title', 'No title'))
        author = clean_field(display.get('creator', '')) or clean_field(addata.get('au', ''))
        publisher = clean_field(display.get('publisher', '')) or clean_field(addata.get('pub', ''))
        year = clean_field(display.get('creationdate', '')) or clean_field(addata.get('date', ''))
        language = clean_field(display.get('language', ''))
        availability = clean_field(display.get('avail', ''))
        subject = clean_field(display.get('subject', ''))
        description = clean_field(display.get('description', ''))

        # Extract year from date strings
        if year != "N/A":
            year_match = re.search(r'\b(19|20)\d{2}\b', year)
            year = year_match.group() if year_match else year

        # Truncate long descriptions
        if len(description) > 200:
            description = description[:200] + "..."

        result_lines = []
        if rank and score is not None:
            result_lines.append(f"RANK #{rank} (Relevance Score: {score:.2f})")

        result_lines.extend([
            f"Title: {title}",
            f"Author: {author if author else 'N/A'}",
            f"Publisher: {publisher if publisher else 'N/A'}",
            f"Year: {year}",
            f"Language: {language}",
            f"Availability: {availability if availability else 'N/A'}",
            f"Subject: {subject if subject else 'N/A'}",
            f"Description: {description if description else 'N/A'}",
            f"Link: https://86sjt-primo.hosted.exlibrisgroup.com.cn/primo-explore/fulldisplay?docid={docId}&vid=book&search_scope=book_journal&tab=default_tab&lang=zh_CN&context=L&isFrbr=true"
        ])

        return '\n'.join(result_lines)

    except Exception as e:
        return f"Error formatting result: {str(e)}"


# @mcp.tool(description="Find the best matched library search results based on relevance scoring")
def search_library_best_match(
        query: str,
        language: str = None,
        advanced: bool = False,
        max_results: int = 1
) -> str:
    """Find the best matched library search results.
    
    Args:
        query: Search query string
        max_results: Maximum number of best results to return (default: 1)
        
    Returns:
        Formatted string with the best matched results ranked by relevance score
    """
    query = (query or "").strip()
    if not query:
        return "Please provide a non-empty search query."

    if max_results < 1:
        max_results = 1
    elif max_results > 10:
        max_results = 10

    try:
        # Initialize library search client and perform search
        client = LibSearchClient()
        result = client.search(query, language, advanced)

        # Extract documents from the response
        docs = result.get('docs', [])
        if not docs:
            return f"No results found for query: {query}"

        # Extract query terms for relevance scoring
        query_terms = re.findall(r'\b\w+\b', query.lower())

        # Calculate relevance scores and sort
        scored_docs = []
        for doc in docs:
            score = _calculate_relevance_score(doc, query_terms)
            scored_docs.append((doc, score))

        # Sort by score (highest first) and take top results
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        top_results = scored_docs[:max_results]

        # Format results
        formatted_results = []
        for i, (doc, score) in enumerate(top_results, 1):
            formatted_result = _format_search_result(doc, rank=i, score=score)
            formatted_results.append(formatted_result)

        return '\n\n' + '\n\n'.join(formatted_results)

    except Exception as e:
        return f"Error searching library: {str(e)}"


# @mcp.tool(description="Search library and return multiple results ranked by relevance. You can use any keywords to search.")
def simple_search_library_ranked(
        query: str,
        max_results: int = 10
) -> str:
    """Search library and return multiple results ranked by relevance score.
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return (default: 5)
        
    Returns:
        Formatted string with multiple results ranked by relevance score
    """
    return search_library_best_match(query, None, False, max_results)


MCP_DESCRIPTION1 = '''
"Advanced Search library and return multiple results ranked by relevance. "
                "For the primo_search_query, you must use query for Primo Library API, "
                "e.g. 'any,contains,Python', 'title,contains,计算机,OR;sub,contains,量子,AND'"
'''

MCP_DESCRIPTION = '''
Executes an advanced search via the Primo Library Discovery API and returns multiple results ranked by relevance.

The `primo_search_query` parameter must be a valid query string formatted for the Primo API.
**Query Format:** `{field},{operator},{value}` (e.g., `title,contains,Quantum Computing`).
**Complex Queries:** Combine multiple conditions using boolean operators (`AND`, `OR`) separated by semicolons `;` (e.g., `title,contains,计算机,OR;sub,contains,量子,AND`).

The `language` parameter is optional and specifies the language of the search query. E.g. "eng" for English and "chi" for Chinese. By default, don't specify a language.
This tool is designed for precise retrieval of academic resources like books, articles, and journals.
'''


@mcp.tool(
    description=MCP_DESCRIPTION
)
def advanced_search_library_ranked(
        primo_search_query: str,
        language: str | None = None,
        max_results: int = 10
) -> str:
    """Search library and return multiple results ranked by relevance score.

    Args:
        primo_search_query: Search query string
        language: Language code (e.g., "eng", "chi")
        max_results: Maximum number of results to return (default: 5)

    Returns:
        Formatted string with multiple results ranked by relevance score
    """
    return search_library_best_match(primo_search_query, language, True, max_results)


def main() -> None:
    """Entry point to run the MCP server."""
    mcp.run(transport='http')


if __name__ == "__main__":
    main()
