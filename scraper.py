"""
TicoViz Corporation v2 — MP4: Web Scraper & Trend Analyzer
Busca leads potenciales en plataformas y analiza tendencias.
"""
import logging
import re
import asyncio
from typing import List, Dict
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from config import MAX_SCRAPER_RESULTS
from models import Lead

logger = logging.getLogger("ticoviz.mp4")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
}


# ==================== BUSQUEDA EN PLATAFORMAS ====================

def buscar_en_google(query: str, max_results: int = 10) -> List[Dict]:
    """Busca en Google resultados relevantes para encontrar leads."""
    results = []
    try:
        search_url = "https://www.google.com/search"
        params = {"q": query, "num": max_results, "hl": "en"}
        resp = requests.get(search_url, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        for g in soup.select("div.g"):
            title_el = g.select_one("h3")
            link_el = g.select_one("a[href]")
            snippet_el = g.select_one("div.VwiC3b") or g.select_one("span.aCOpRe")

            if title_el and link_el:
                href = link_el.get("href", "")
                if href.startswith("/url?q="):
                    href = href.split("/url?q=")[1].split("&")[0]
                results.append({
                    "titulo": title_el.get_text(strip=True),
                    "url": href,
                    "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                    "fuente": "google",
                })
        logger.info(f"MP4 Google: {len(results)} resultados para '{query}'")
    except Exception as e:
        logger.error(f"MP4 Error buscando en Google: {e}")
    return results[:max_results]


def buscar_github_repos(query: str, max_results: int = 10) -> List[Dict]:
    """Busca repos en GitHub que indiquen demanda de un producto."""
    results = []
    try:
        api_url = "https://api.github.com/search/repositories"
        params = {"q": query, "sort": "stars", "order": "desc", "per_page": max_results}
        resp = requests.get(api_url, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        for repo in data.get("items", []):
            results.append({
                "titulo": repo["full_name"],
                "url": repo["html_url"],
                "snippet": repo.get("description", ""),
                "stars": repo["stargazers_count"],
                "language": repo.get("language", ""),
                "updated": repo.get("updated_at", ""),
                "fuente": "github",
            })
        logger.info(f"MP4 GitHub: {len(results)} repos para '{query}'")
    except Exception as e:
        logger.error(f"MP4 Error buscando en GitHub: {e}")
    return results[:max_results]


def buscar_reddit(query: str, max_results: int = 10) -> List[Dict]:
    """Busca posts en Reddit que indiquen demanda."""
    results = []
    try:
        search_url = f"https://www.reddit.com/search.json"
        params = {"q": query, "sort": "relevance", "limit": max_results, "t": "month"}
        resp = requests.get(search_url, params=params,
                           headers={**HEADERS, "Accept": "application/json"}, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        for post in data.get("data", {}).get("children", []):
            p = post["data"]
            results.append({
                "titulo": p.get("title", ""),
                "url": f"https://reddit.com{p.get('permalink', '')}",
                "snippet": p.get("selftext", "")[:200],
                "score": p.get("score", 0),
                "subreddit": p.get("subreddit", ""),
                "comments": p.get("num_comments", 0),
                "fuente": "reddit",
            })
        logger.info(f"MP4 Reddit: {len(results)} posts para '{query}'")
    except Exception as e:
        logger.error(f"MP4 Error buscando en Reddit: {e}")
    return results[:max_results]


def buscar_stackoverflow(query: str, max_results: int = 10) -> List[Dict]:
    """Busca preguntas en StackOverflow que indiquen demanda."""
    results = []
    try:
        api_url = "https://api.stackexchange.com/2.3/search/advanced"
        params = {
            "q": query,
            "order": "desc",
            "sort": "relevance",
            "site": "stackoverflow",
            "pagesize": max_results,
            "filter": "default",
        }
        resp = requests.get(api_url, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        for item in data.get("items", []):
            results.append({
                "titulo": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": ", ".join(item.get("tags", [])),
                "score": item.get("score", 0),
                "answers": item.get("answer_count", 0),
                "views": item.get("view_count", 0),
                "fuente": "stackoverflow",
            })
        logger.info(f"MP4 StackOverflow: {len(results)} preguntas para '{query}'")
    except Exception as e:
        logger.error(f"MP4 Error buscando en StackOverflow: {e}")
    return results[:max_results]


# ==================== RASTREO DE LEADS ====================

def rastrear_leads(producto_nombre: str, categoria: str,
                   tecnologias: str = "") -> List[Dict]:
    """
    MP4 — Busca leads potenciales en multiples plataformas.
    Combina resultados de Google, GitHub, Reddit y StackOverflow.
    """
    queries = [
        f"need {producto_nombre} freelance",
        f"looking for {categoria} developer",
        f"hire someone to build {producto_nombre}",
    ]
    if tecnologias:
        queries.append(f"{tecnologias} project help needed")

    all_results = []
    max_per_source = MAX_SCRAPER_RESULTS // 4

    for query in queries[:2]:
        all_results.extend(buscar_en_google(query, max_per_source))
        all_results.extend(buscar_github_repos(query, max_per_source))
        all_results.extend(buscar_reddit(query, max_per_source))
        all_results.extend(buscar_stackoverflow(query, max_per_source))

    # Deduplicar por URL
    seen = set()
    unique = []
    for r in all_results:
        url = r.get("url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(r)

    logger.info(f"MP4: Rastreo completo — {len(unique)} leads unicos encontrados")
    return unique[:MAX_SCRAPER_RESULTS]


def rastrear_y_clasificar(producto_nombre: str, categoria: str,
                           tecnologias: str = "") -> List[Lead]:
    """
    Busca leads y los convierte a objetos Lead con scoring basico.
    """
    resultados = rastrear_leads(producto_nombre, categoria, tecnologias)
    leads = []

    for r in resultados:
        # Scoring basico por fuente
        score_base = {
            "reddit": 60,
            "stackoverflow": 50,
            "google": 40,
            "github": 30,
        }.get(r.get("fuente", ""), 20)

        # Bonus por engagement
        if r.get("score", 0) > 10:
            score_base += 10
        if r.get("comments", 0) > 5:
            score_base += 10

        lead = Lead(
            nombre=r.get("titulo", "")[:100],
            contacto="",
            plataforma=r.get("fuente", ""),
            necesidad=r.get("snippet", "")[:200],
            presupuesto_estimado=0,
            score=min(score_base, 100),
            url=r.get("url", ""),
        )
        leads.append(lead)

    # Ordenar por score
    leads.sort(key=lambda x: x.score, reverse=True)
    return leads
