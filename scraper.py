import hashlib
import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

# Tenta usar curl_cffi (impersonate="chrome") para contornar bloqueios Cloudflare
# (essencial para Indeed, InfoJobs e Catho). Caso não esteja disponível, usa requests padrão.
try:
    from curl_cffi import requests as cffi_requests

    TEM_CURL_CFFI = True
except ImportError:
    cffi_requests = None
    TEM_CURL_CFFI = False

HEADERS_PADRAO = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}

TIMEOUT_PADRAO = 15


def fazer_get(url: str, params: dict | None = None, headers: dict | None = None, usar_impersonate: bool = True):
    """Realiza requisição HTTP GET usando curl_cffi (impersonate Chrome) ou requests padrão."""
    hdrs = headers or HEADERS_PADRAO
    if usar_impersonate and TEM_CURL_CFFI:
        return cffi_requests.get(url, params=params, headers=hdrs, impersonate="chrome", timeout=TIMEOUT_PADRAO)
    return requests.get(url, params=params, headers=hdrs, timeout=TIMEOUT_PADRAO)


def remover_acentos(texto: str) -> str:
    """Remove acentos de uma string (ex: 'Estágio Edificações' -> 'Estagio Edificacoes')."""
    if not texto:
        return ""
    normalizado = unicodedata.normalize("NFKD", texto)
    return normalizado.encode("ascii", "ignore").decode("ascii")


def gerar_slug(texto: str) -> str:
    """Converte um texto para formato slug de URL sem acentos (ex: 'estagio-desenvolvimento')."""
    sem_acento = remover_acentos(texto.lower())
    return re.sub(r"[^a-z0-9]+", "-", sem_acento).strip("-")


def limpar_texto(texto: str) -> str:
    """Remove espaços extras, quebras de linha duplicadas e tags HTML residuais."""
    if not texto:
        return ""
    texto_sem_html = BeautifulSoup(str(texto), "html.parser").get_text(separator=" ")
    return re.sub(r"\s+", " ", texto_sem_html).strip()


def gerar_id_vaga(titulo: str, empresa: str, link: str) -> str:
    """Gera um identificador único (hash MD5) para evitar avaliar a mesma vaga duas vezes."""
    link_limpo = (link or "").split("?")[0].strip().lower()
    base = link_limpo if link_limpo else f"{titulo.lower().strip()}|{empresa.lower().strip()}"
    return hashlib.md5(base.encode("utf-8")).hexdigest()


def normalizar_vaga(
    titulo: str,
    descricao: str,
    link: str,
    fonte: str,
    empresa: str = "Não informada",
    local: str = "Não informado",
    salario: str = "Não informado",
    modalidade: str = "",
) -> dict:
    """Padroniza o dicionário de vaga retornado por qualquer plataforma."""
    titulo_limpo = limpar_texto(titulo)
    empresa_limpa = limpar_texto(empresa) or "Não informada"
    local_limpo = limpar_texto(local) or "Não informado"
    descricao_limpa = limpar_texto(descricao)

    detalhes_extras = []
    if empresa_limpa and empresa_limpa != "Não informada":
        detalhes_extras.append(f"Empresa: {empresa_limpa}")
    if local_limpo and local_limpo != "Não informado":
        detalhes_extras.append(f"Localização: {local_limpo}")
    if modalidade:
        detalhes_extras.append(f"Modalidade: {limpar_texto(modalidade)}")
    if salario and salario != "Não informado":
        detalhes_extras.append(f"Salário: {limpar_texto(salario)}")
    detalhes_extras.append(f"Fonte: {fonte}")

    cabecalho = " | ".join(detalhes_extras)
    descricao_completa = f"[{cabecalho}]\n{descricao_limpa}" if descricao_limpa else f"[{cabecalho}]"

    return {
        "id": gerar_id_vaga(titulo_limpo, empresa_limpa, link),
        "titulo": titulo_limpo,
        "empresa": empresa_limpa,
        "local": local_limpo,
        "salario": limpar_texto(salario) or "Não informado",
        "modalidade": limpar_texto(modalidade),
        "descricao": descricao_completa[:4000],
        "link": (link or "").strip(),
        "fonte": fonte,
    }


# ==============================================================================
# 1. GUPY (Portal Oficial Gupy via NextData JSON)
# ==============================================================================
def _consultar_gupy_termo(termo: str) -> list[dict]:
    """Faz a requisição ao portal Gupy e retorna a lista bruta de vagas do NextData."""
    url = f"https://portal.gupy.io/job-search/term={quote(termo)}"
    resp = fazer_get(url, usar_impersonate=False)
    if resp.status_code != 200:
        return []

    sopa = BeautifulSoup(resp.text, "html.parser")
    script_next = sopa.find("script", id="__NEXT_DATA__")
    if not script_next or not script_next.string:
        return []

    dados_next = json.loads(script_next.string)
    initial_jobs = (
        dados_next.get("props", {})
        .get("pageProps", {})
        .get("initialJobList", {})
    )
    return initial_jobs.get("data", []) if isinstance(initial_jobs, dict) else []


def raspar_gupy(termo: str, local: str = "", limite: int = 8) -> list[dict]:
    """Busca vagas diretamente no Portal Gupy (portal.gupy.io)."""
    vagas = []

    try:
        dados = _consultar_gupy_termo(termo)
        # Como a Gupy faz busca exata de substring no título, termos compostos (ex: "Estágio Python")
        # podem vir vazios; nesse caso, busca pela palavra-chave principal do termo.
        if not dados and " " in termo.strip():
            palavras = [p for p in termo.split() if len(p) > 2 and p.lower() not in ("em", "de", "da", "do")]
            if palavras:
                palavra_foco = palavras[-1] if palavras[0].lower().startswith(("est", "des", "aux", "ana")) else palavras[0]
                dados = _consultar_gupy_termo(palavra_foco)

        for item in dados:
            titulo = item.get("name", "")
            empresa = item.get("careerPageName", "Empresa na Gupy")
            cidade = item.get("city", "")
            estado = item.get("state", "")
            remoto = item.get("isRemoteWork", False)
            tipo_trabalho = item.get("workplaceType", "")  # remote, hybrid, on-site

            local_vaga = " / ".join(filter(None, [cidade, estado])) or "Brasil"
            if remoto or tipo_trabalho == "remote":
                modalidade = "100% Remoto"
            elif tipo_trabalho == "hybrid":
                modalidade = "Híbrido"
            elif tipo_trabalho == "on-site":
                modalidade = "Presencial"
            else:
                modalidade = ""

            # Filtra por cidade caso a vaga não seja remota e tenha cidade especificada
            if local and local.lower() not in ("brasil", "remoto", ""):
                local_vaga_sem_acento = remover_acentos(f"{cidade} {estado}").lower()
                local_alvo_sem_acento = remover_acentos(local).lower()
                if not remoto and tipo_trabalho != "remote":
                    if (
                        local_alvo_sem_acento not in local_vaga_sem_acento
                        and local_vaga_sem_acento.strip() != ""
                    ):
                        continue

            descricao = item.get("description", "")
            link = item.get("jobUrl", "")

            if titulo and link:
                vagas.append(
                    normalizar_vaga(
                        titulo=titulo,
                        descricao=descricao,
                        link=link,
                        fonte="Gupy",
                        empresa=empresa,
                        local=f"{local_vaga} ({modalidade})" if modalidade else local_vaga,
                        modalidade=modalidade,
                    )
                )
                if len(vagas) >= limite:
                    break
    except Exception as e:
        print(f"  [Gupy] Aviso ao buscar '{termo}': {e}")

    return vagas


# ==============================================================================
# 2. LINKEDIN (API Guest de Vagas Pública do LinkedIn)
# ==============================================================================
def _buscar_descricao_linkedin(job_id: str) -> str:
    """Busca a descrição completa de uma vaga no LinkedIn usando o endpoint público."""
    if not job_id:
        return ""
    url_detalhe = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
    try:
        resp = requests.get(url_detalhe, headers=HEADERS_PADRAO, timeout=10)
        if resp.status_code == 200:
            sopa = BeautifulSoup(resp.text, "html.parser")
            bloco_desc = (
                sopa.find("div", class_="show-more-less-html__markup")
                or sopa.find("div", class_="description__text")
                or sopa.find("section", class_="show-more-less-html")
            )
            criterios = sopa.find_all("li", class_="description__job-criteria-item")
            texto_criterios = " | ".join(limpar_texto(c.get_text()) for c in criterios)
            texto_desc = limpar_texto(bloco_desc.get_text()) if bloco_desc else ""
            if texto_criterios:
                return f"{texto_criterios}. {texto_desc}"
            return texto_desc
    except Exception:
        pass
    return ""


def raspar_linkedin(termo: str, local: str = "Brasil", limite: int = 6) -> list[dict]:
    """Busca vagas recentes no LinkedIn via endpoint Guest Jobs e coleta suas descrições."""
    vagas = []
    url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    params = {
        "keywords": termo,
        "location": local or "Brasil",
        "f_TPR": "r604800",  # Últimos 7 dias
        "start": 0,
    }

    try:
        resp = fazer_get(url, params=params, usar_impersonate=False)
        if resp.status_code != 200:
            return vagas

        sopa = BeautifulSoup(resp.text, "html.parser")
        cards = sopa.find_all("li") or sopa.find_all("div", class_="base-card")

        for card in cards[:limite]:
            bloco_base = card.find("div", class_="base-card") or card
            urn = bloco_base.get("data-entity-urn", "")
            job_id = urn.split(":")[-1] if ":" in urn else ""

            tag_titulo = card.find("h3", class_="base-search-card__title") or card.find("h3")
            tag_empresa = card.find("h4", class_="base-search-card__subtitle") or card.find("h4")
            tag_local = card.find("span", class_="job-search-card__location")
            tag_link = card.find("a", class_="base-card__full-link") or card.find("a", href=True)

            if not tag_titulo or not tag_link:
                continue

            titulo = limpar_texto(tag_titulo.get_text())
            empresa = limpar_texto(tag_empresa.get_text()) if tag_empresa else "Empresa no LinkedIn"
            local_vaga = limpar_texto(tag_local.get_text()) if tag_local else local
            link = tag_link["href"].split("?")[0]

            if not job_id:
                match_id = re.search(r"-(\d{7,})(?:[/?]|$)", link)
                if match_id:
                    job_id = match_id.group(1)

            descricao = _buscar_descricao_linkedin(job_id)
            if not descricao:
                descricao = f"Vaga de {titulo} na empresa {empresa} em {local_vaga}."

            vagas.append(
                normalizar_vaga(
                    titulo=titulo,
                    descricao=descricao,
                    link=link,
                    fonte="LinkedIn",
                    empresa=empresa,
                    local=local_vaga,
                )
            )
    except Exception as e:
        print(f"  [LinkedIn] Aviso ao buscar '{termo}': {e}")

    return vagas


# ==============================================================================
# 3. INDEED BRASIL (Extração de Dados Estruturados via Chrome Impersonation)
# ==============================================================================
def raspar_indeed(termo: str, local: str = "Brasil", limite: int = 8) -> list[dict]:
    """Busca vagas recentes no Indeed Brasil (br.indeed.com)."""
    vagas = []
    url = "https://br.indeed.com/jobs"
    params = {
        "q": termo,
        "l": "" if local.lower() == "brasil" else local,
        "fromage": "7",
        "sort": "date",
    }

    try:
        resp = fazer_get(url, params=params, usar_impersonate=True)
        if resp.status_code == 200 and "mosaic-provider-jobcards" in resp.text:
            match = re.search(
                r'window\.mosaic\.providerData\["mosaic-provider-jobcards"\]\s*=\s*(\{.*?\});\s*\n',
                resp.text,
                re.DOTALL,
            )
            if match:
                dados_json = json.loads(match.group(1))
                resultados = (
                    dados_json.get("metaData", {})
                    .get("mosaicProviderJobCardsModel", {})
                    .get("results", [])
                )
                for item in resultados[:limite]:
                    jobkey = item.get("jobkey", "")
                    titulo = item.get("title", "")
                    empresa = item.get("company", "Empresa no Indeed")
                    local_vaga = item.get("formattedLocation", local)
                    snippet = item.get("snippet", "")
                    taxonomia = item.get("taxonomyAttributes", [])
                    texto_extra = []
                    for attr in taxonomia:
                        attrs = attr.get("attributes", [])
                        for a in attrs:
                            if a.get("label"):
                                texto_extra.append(a["label"])

                    salario = item.get("extractedSalary") or item.get("salarySnippet", {})
                    texto_salario = "Não informado"
                    if isinstance(salario, dict):
                        if salario.get("text"):
                            texto_salario = salario["text"]
                        elif salario.get("min"):
                            texto_salario = f"R$ {salario.get('min')} - R$ {salario.get('max')}"

                    link = f"https://br.indeed.com/viewjob?jk={jobkey}" if jobkey else ""
                    descricao_completa = f"{' | '.join(texto_extra)}. {snippet}" if texto_extra else snippet

                    if titulo and link:
                        vagas.append(
                            normalizar_vaga(
                                titulo=titulo,
                                descricao=descricao_completa,
                                link=link,
                                fonte="Indeed",
                                empresa=empresa,
                                local=local_vaga,
                                salario=texto_salario,
                            )
                        )
    except Exception as e:
        print(f"  [Indeed] Aviso ao buscar '{termo}': {e}")

    return vagas


# ==============================================================================
# 4. INFOJOBS BRASIL (Raspagem Completa de Cards e Salários)
# ==============================================================================
def raspar_infojobs(termo: str, local: str = "", limite: int = 8) -> list[dict]:
    """Busca vagas no InfoJobs Brasil (infojobs.com.br)."""
    vagas = []
    termo_busca = f"{termo} {local}".strip() if local and local.lower() != "brasil" else termo
    url = "https://www.infojobs.com.br/empregos.aspx"
    params = {"palabra": termo_busca}

    try:
        resp = fazer_get(url, params=params, usar_impersonate=True)
        if resp.status_code == 200:
            sopa = BeautifulSoup(resp.text, "html.parser")
            cards = sopa.select("div.js_rowCard")

            for card in cards[:limite]:
                tag_titulo = card.select_one("h2.js_vacancyTitle, h2")
                tag_link = card.select_one("a[href*='/vaga-de-'], a.text-decoration-none[href]")
                tag_empresa = card.select_one("div.text-body a, div.text-body")
                tag_local = card.select_one("div.text-medium.small, div.mb-8")
                tag_faixa = card.select_one("div.d-inline-flex.flex-wrap")
                blocos_texto = card.select("div.text-medium")

                if not tag_titulo or not tag_link:
                    continue

                titulo = limpar_texto(tag_titulo.get_text())
                link = urljoin("https://www.infojobs.com.br", tag_link.get("href", ""))
                empresa = limpar_texto(tag_empresa.get_text()) if tag_empresa else "Empresa no InfoJobs"
                local_vaga = limpar_texto(tag_local.get_text()).split(",")[0] if tag_local else (local or "Brasil")
                faixa_detalhes = limpar_texto(tag_faixa.get_text()) if tag_faixa else ""
                desc_vaga = limpar_texto(blocos_texto[-1].get_text()) if blocos_texto else titulo

                descricao_final = f"{faixa_detalhes}. {desc_vaga}" if faixa_detalhes else desc_vaga

                vagas.append(
                    normalizar_vaga(
                        titulo=titulo,
                        descricao=descricao_final,
                        link=link,
                        fonte="InfoJobs",
                        empresa=empresa,
                        local=local_vaga,
                        salario=faixa_detalhes if "R$" in faixa_detalhes else "Não informado",
                    )
                )
    except Exception as e:
        print(f"  [InfoJobs] Aviso ao buscar '{termo}': {e}")

    return vagas


# ==============================================================================
# 5. VAGAS.COM.BR (Raspagem Direta HTML)
# ==============================================================================
def raspar_vagas_com(termo: str, local: str = "", limite: int = 8) -> list[dict]:
    """Busca vagas no portal Vagas.com.br."""
    vagas = []
    slug = gerar_slug(termo)
    url = f"https://www.vagas.com.br/vagas-de-{slug}"

    try:
        resp = fazer_get(url, usar_impersonate=False)
        if resp.status_code != 200:
            return vagas

        sopa = BeautifulSoup(resp.text, "html.parser")
        cards = sopa.find_all("li", class_="vaga")

        for card in cards:
            tag_link = card.find("a", class_="link-detalhes-vaga")
            tag_empresa = card.find("span", class_="emprVaga")
            tag_nivel = card.find("span", class_="nivelVaga")
            tag_local = card.find("span", class_="vaga-local")
            tag_desc = card.find("div", class_="detalhes")

            if not tag_link:
                continue

            titulo = tag_link.get("title") or tag_link.get_text()
            link = urljoin("https://www.vagas.com.br", tag_link.get("href", ""))
            empresa = tag_empresa.get_text() if tag_empresa else "Empresa no Vagas.com"
            local_vaga = limpar_texto(tag_local.get_text()) if tag_local else "Brasil"
            nivel = limpar_texto(tag_nivel.get_text()) if tag_nivel else ""
            descricao = limpar_texto(tag_desc.get_text()) if tag_desc else ""
            if nivel:
                descricao = f"Nível: {nivel}. {descricao}"

            # Se o perfil pediu uma cidade específica, aceita vagas da cidade, remotas ou nacionais
            if local and local.lower() not in ("brasil", "remoto", ""):
                loc_norm = remover_acentos(local_vaga).lower()
                alvo_norm = remover_acentos(local).lower()
                if (
                    alvo_norm not in loc_norm
                    and "remoto" not in loc_norm
                    and "home office" not in loc_norm
                    and "todo o brasil" not in loc_norm
                    and loc_norm not in ("brasil", "nao informado", "")
                ):
                    continue

            vagas.append(
                normalizar_vaga(
                    titulo=titulo,
                    descricao=descricao,
                    link=link,
                    fonte="Vagas.com.br",
                    empresa=empresa,
                    local=local_vaga,
                )
            )
            if len(vagas) >= limite:
                break
    except Exception as e:
        print(f"  [Vagas.com.br] Aviso ao buscar '{termo}': {e}")

    return vagas


# ==============================================================================
# 6. TRABALHA BRASIL (Excelente para Edificações, Técnico e Júnior/Estágio)
# ==============================================================================
MAPA_CIDADES_TRABALHA_BRASIL = {
    "curitiba": "curitiba-pr",
    "rio de janeiro": "rio-de-janeiro-rj",
    "sao paulo": "sao-paulo-sp",
}


def raspar_trabalha_brasil(termo: str, local: str = "", limite: int = 8) -> list[dict]:
    """Busca vagas no portal Trabalha Brasil (trabalhabrasil.com.br)."""
    vagas = []
    slug_termo = gerar_slug(termo)
    local_chave = remover_acentos(local).lower().strip()
    slug_cidade = MAPA_CIDADES_TRABALHA_BRASIL.get(local_chave, "")

    if slug_cidade:
        url = f"https://www.trabalhabrasil.com.br/vagas-empregos-em-{slug_cidade}/{slug_termo}"
    else:
        url = f"https://www.trabalhabrasil.com.br/vagas-empregos/{slug_termo}"

    try:
        resp = fazer_get(url, usar_impersonate=False)
        if resp.status_code != 200:
            return vagas

        sopa = BeautifulSoup(resp.text, "html.parser")
        cards = sopa.select("a.job-link, a.jobCard, div.jg__job")

        for card in cards[:limite]:
            tag_titulo = card.select_one("h2.job-title, h2.job__name, h2, h3")
            tag_empresa = card.select_one("p.job-company, h3.job__company")
            tag_local = card.select_one("p.job-location, h3.job__detail")
            tag_salario = card.select_one("span.salary")
            tag_modalidade = card.select_one("span.workplace")
            tag_regime = card.select_one("span.employment-type")
            tag_desc = card.select_one("p.job__description")

            link_rel = card.get("href") or card.get("data-job-url") or ""
            if not tag_titulo or not link_rel:
                continue

            link = urljoin("https://www.trabalhabrasil.com.br", link_rel)
            titulo = limpar_texto(tag_titulo.get_text())
            empresa = limpar_texto(tag_empresa.get_text()) if tag_empresa else "Empresa no Trabalha Brasil"
            local_vaga = limpar_texto(tag_local.get_text()) if tag_local else (local or "Brasil")
            salario = limpar_texto(tag_salario.get_text()) if tag_salario else "Não informado"
            modalidade = limpar_texto(tag_modalidade.get_text()) if tag_modalidade else ""
            regime = limpar_texto(tag_regime.get_text()) if tag_regime else ""
            desc_extra = limpar_texto(tag_desc.get_text()) if tag_desc else ""

            partes_desc = [
                f"Vaga: {titulo}",
                f"Regime: {regime}" if regime else "",
                f"Modalidade: {modalidade}" if modalidade else "",
                f"Remuneração: {salario}" if salario != "Não informado" else "",
                desc_extra,
            ]
            descricao = " | ".join(filter(None, partes_desc))

            vagas.append(
                normalizar_vaga(
                    titulo=titulo,
                    descricao=descricao,
                    link=link,
                    fonte="Trabalha Brasil",
                    empresa=empresa,
                    local=local_vaga,
                    salario=salario,
                    modalidade=modalidade,
                )
            )
    except Exception as e:
        print(f"  [Trabalha Brasil] Aviso ao buscar '{termo}': {e}")

    return vagas


# ==============================================================================
# 7. CATHO (Raspagem via JSON NextData / HTML)
# ==============================================================================
def raspar_catho(termo: str, local: str = "", limite: int = 8) -> list[dict]:
    """Busca vagas no portal Catho (catho.com.br)."""
    vagas = []
    slug = gerar_slug(termo)
    url = f"https://www.catho.com.br/vagas/{slug}/"
    params = {"q": f"{termo} {local}"} if local and local.lower() not in ("brasil", "remoto", "") else {}

    try:
        resp = fazer_get(url, params=params, usar_impersonate=True)
        if resp.status_code == 200:
            sopa = BeautifulSoup(resp.text, "html.parser")

            script_next = sopa.find("script", id="__NEXT_DATA__")
            if script_next and script_next.string:
                dados = json.loads(script_next.string)
                lista_vagas = (
                    dados.get("props", {})
                    .get("pageProps", {})
                    .get("jobSearch", {})
                    .get("jobSearchResult", {})
                    .get("data", {})
                    .get("jobs", [])
                )
                for item in lista_vagas[:limite]:
                    job_data = item.get("job_customized_data", item)
                    titulo = job_data.get("titulo", "")
                    descricao = job_data.get("descricao", "")
                    empresa = job_data.get("anunciante", {}).get("nome", "Empresa na Catho")
                    salario = job_data.get("faixa_salarial", "Não informado")
                    regime = job_data.get("regime_contrato", "")
                    vagas_locais = job_data.get("vagas", [{}])
                    cidade_uf = ""
                    if vagas_locais and isinstance(vagas_locais, list):
                        c = vagas_locais[0].get("cidade", "")
                        u = vagas_locais[0].get("uf", "")
                        cidade_uf = f"{c}/{u}".strip("/")
                    job_id = job_data.get("id", "")
                    link = f"https://www.catho.com.br/vagas/{slug}/{job_id}/" if job_id else url

                    if titulo:
                        vagas.append(
                            normalizar_vaga(
                                titulo=titulo,
                                descricao=f"Regime: {regime}. {descricao}" if regime else descricao,
                                link=link,
                                fonte="Catho",
                                empresa=empresa,
                                local=cidade_uf or local or "Brasil",
                                salario=str(salario),
                            )
                        )
    except Exception as e:
        print(f"  [Catho] Aviso ao buscar '{termo}': {e}")

    return vagas


# ==============================================================================
# 8. PROGRAMATHOR (Especializado em Vagas de Tecnologia no Brasil)
# ==============================================================================
def raspar_programathor(termo: str = "", limite: int = 6) -> list[dict]:
    """Busca vagas de tecnologia no portal Programathor."""
    vagas = []
    url = "https://programathor.com.br/jobs"
    params = {"term": remover_acentos(termo)} if termo else {}

    try:
        resp = fazer_get(url, params=params, usar_impersonate=False)
        if resp.status_code != 200:
            return vagas

        sopa = BeautifulSoup(resp.text, "html.parser")
        cards = sopa.select("div.cell-list")

        for card in cards[:limite]:
            tag_a = card.find("a", href=True)
            tag_titulo = card.select_one("h3")
            infos = card.select("div.cell-list-content-icon span")
            tags_skills = card.select("span.tag-list")

            if not tag_titulo or not tag_a:
                continue

            titulo = limpar_texto(tag_titulo.get_text())
            if "vencida" in titulo.lower():
                continue

            link = urljoin("https://programathor.com.br", tag_a["href"])
            detalhes_icone = [limpar_texto(i.get_text()) for i in infos if limpar_texto(i.get_text())]
            skills = [limpar_texto(s.get_text()) for s in tags_skills if limpar_texto(s.get_text())]

            empresa = detalhes_icone[0] if len(detalhes_icone) > 0 else "Empresa no Programathor"
            local_vaga = detalhes_icone[1] if len(detalhes_icone) > 1 else "Brasil"
            descricao = (
                f"Detalhes: {' | '.join(detalhes_icone)}. "
                f"Tecnologias exigidas: {', '.join(skills)}."
            )

            vagas.append(
                normalizar_vaga(
                    titulo=titulo,
                    descricao=descricao,
                    link=link,
                    fonte="Programathor",
                    empresa=empresa,
                    local=local_vaga,
                )
            )
    except Exception as e:
        print(f"  [Programathor] Aviso ao buscar '{termo}': {e}")

    return vagas


# ==============================================================================
# 9. GITHUB VAGAS BRASIL (Comunidades Oficiais Backend-BR, Frontend-BR, etc.)
# ==============================================================================
REPOSITORIOS_GITHUB_TECH = [
    "backend-br/vagas",
    "frontendbr/vagas",
    "react-brasil/vagas",
    "pybr/vagas",
    "datascience-br/vagas",
]


def raspar_github_vagas(limite_por_repo: int = 5) -> list[dict]:
    """Busca vagas abertas nos repositórios brasileiros de tecnologia no GitHub."""
    vagas = []
    headers = {
        **HEADERS_PADRAO,
        "Accept": "application/vnd.github+json",
    }

    for repo in REPOSITORIOS_GITHUB_TECH:
        url = f"https://api.github.com/repos/{repo}/issues"
        params = {"state": "open", "per_page": limite_por_repo}
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            if resp.status_code != 200:
                continue

            issues = resp.json()
            for issue in issues:
                if "pull_request" in issue:
                    continue
                titulo = issue.get("title", "")
                corpo = issue.get("body", "") or ""
                link = issue.get("html_url", "")
                labels = [lb.get("name", "") for lb in issue.get("labels", [])]
                texto_labels = ", ".join(filter(None, labels))

                vagas.append(
                    normalizar_vaga(
                        titulo=titulo,
                        descricao=f"Labels: [{texto_labels}]\n{corpo}",
                        link=link,
                        fonte=f"GitHub ({repo.split('/')[0]})",
                        empresa=repo,
                        local=texto_labels or "Brasil / Remoto",
                    )
                )
        except Exception:
            continue

    return vagas


# ==============================================================================
# ORQUESTRADOR PRINCIPAL DE RASPAGEM MULTI-FONTES
# ==============================================================================
def buscar_vagas(
    termos_busca: list[str] | None = None,
    localizacoes: list[str] | None = None,
    incluir_fontes_tech: bool = True,
    limite_por_fonte: int = 5,
) -> list[dict]:
    """
    Vasculha simultaneamente múltiplas plataformas de emprego:
    LinkedIn, Gupy, Indeed, InfoJobs, Vagas.com.br, Catho, Trabalha Brasil,
    Programathor e GitHub Vagas BR.
    Retorna uma lista de vagas únicas e padronizadas.
    """
    if not termos_busca:
        termos_busca = [
            "Desenvolvedor Python Júnior",
            "Estágio Desenvolvimento",
            "Full Stack Júnior",
        ]
    if not localizacoes:
        localizacoes = ["Brasil"]

    local_principal = localizacoes[0] if localizacoes else "Brasil"
    print(
        f"\n🔎 Iniciando varredura em múltiplas fontes para {len(termos_busca)} termo(s) "
        f"(Local foco: {local_principal})..."
    )

    tarefas = []
    vagas_coletadas = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        for termo in termos_busca:
            # 1. Gupy
            tarefas.append(executor.submit(raspar_gupy, termo, local_principal, limite_por_fonte))
            # 2. LinkedIn (Local específico + Remoto Brasil)
            tarefas.append(executor.submit(raspar_linkedin, termo, local_principal, limite_por_fonte))
            if local_principal.lower() not in ("brasil", "remoto"):
                tarefas.append(executor.submit(raspar_linkedin, f"{termo} remoto", "Brasil", 3))
            # 3. Indeed Brasil
            tarefas.append(executor.submit(raspar_indeed, termo, local_principal, limite_por_fonte))
            # 4. InfoJobs Brasil
            tarefas.append(executor.submit(raspar_infojobs, termo, local_principal, limite_por_fonte))
            # 5. Vagas.com.br
            tarefas.append(executor.submit(raspar_vagas_com, termo, local_principal, limite_por_fonte))
            # 6. Trabalha Brasil
            tarefas.append(executor.submit(raspar_trabalha_brasil, termo, local_principal, limite_por_fonte))
            # 7. Catho
            tarefas.append(executor.submit(raspar_catho, termo, local_principal, limite_por_fonte))

            # 8. Fontes exclusivas de Tecnologia (Programathor)
            if incluir_fontes_tech:
                tarefas.append(executor.submit(raspar_programathor, termo, 4))

        # 9. Repositórios GitHub Vagas BR (para perfis de tecnologia)
        if incluir_fontes_tech:
            tarefas.append(executor.submit(raspar_github_vagas, 4))

        for futuro in as_completed(tarefas):
            try:
                resultado = futuro.result()
                if resultado:
                    vagas_coletadas.extend(resultado)
            except Exception as e:
                print(f"  [Aviso] Erro em uma subtarefa de raspagem: {e}")

    # Desduplicação das vagas encontradas nesta execução (por ID ou Título+Empresa)
    vagas_unicas = {}
    chaves_titulo_empresa = set()

    for vaga in vagas_coletadas:
        id_vaga = vaga["id"]
        chave_te = f"{vaga['titulo'].lower()}|{vaga['empresa'].lower()}"
        if id_vaga not in vagas_unicas and chave_te not in chaves_titulo_empresa:
            vagas_unicas[id_vaga] = vaga
            chaves_titulo_empresa.add(chave_te)

    lista_final = list(vagas_unicas.values())

    contagem_fontes = {}
    for v in lista_final:
        fonte = v["fonte"]
        contagem_fontes[fonte] = contagem_fontes.get(fonte, 0) + 1

    resumo_fontes = ", ".join(f"{f}: {qtd}" for f, qtd in sorted(contagem_fontes.items()))
    print(f"✅ Total de {len(lista_final)} vagas únicas encontradas! ({resumo_fontes or 'Nenhuma'})")

    return lista_final
