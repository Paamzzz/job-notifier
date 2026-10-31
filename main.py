import json
import os
import re
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from google import genai

from scraper import buscar_vagas

load_dotenv()  # Carrega variáveis do arquivo .env

CHAVE_API = (os.getenv("GOOGLE_KEY") or "").strip()
MODELO_PREFERIDO = (os.getenv("GEMINI_MODEL") or "gemini-2.5-flash").strip()
ARQUIVO_HISTORICO = "historico_vagas.json"
LIMITE_AVALIACOES_IA_POR_PERFIL = int(os.getenv("LIMITE_VAGAS_POR_PERFIL", "60"))
TAMANHO_LOTE_IA = int(os.getenv("TAMANHO_LOTE_IA", "10"))

client = genai.Client(api_key=CHAVE_API) if CHAVE_API else None

perfis_busca = [
    {
        "nome": "Nycollas - Edificações",
        "ativo": True,
        "webhook_url": (os.getenv("WEBHOOK_EDIFICACOES") or "").strip(),
        "incluir_fontes_tech": False,
        "localizacoes": ["Curitiba", "Brasil"],
        "termos_busca": [
            "Técnico em Edificações",
            "Cadista",
            "Desenhista Cadista",
            "Desenhista Técnico",
            "Auxiliar de Engenharia Civil",
            "Auxiliar de Arquitetura",
            "Projetista AutoCAD",
            "Vistoriador de Imóveis",
            "Orçamentista Obras",
        ],
        "palavras_bloqueadas_titulo": [
            "sênior",
            "senior",
            "sr.",
            "coordenador",
            "gerente",
            "engenheiro civil sênior",
            "engenheiro civil pleno",
            "arquiteto sênior",
            "diretor",
        ],
        "prompt_filtro": """
                     Você é um recrutador sênior. Avalie a vaga abaixo para o meu perfil.

                    1. VAGAS DESEJADAS
                      técnico em edificações, cadista, auxiliar de arquiteto, auxiliar de engenheiro civil,
                      projetista, desenhista cadista, desenhista técnico, vistoriador, analista de orçamentos e planejamentos

                    2. REGRAS ELIMINATÓRIAS (Se violar QUALQUER uma, a vaga está reprovada):
                    - Vagas que o salário é abaixo de R$2.100 (Se o salário não estiver informado na descrição, NÃO elimine a vaga por este critério)
                    - Vagas Pj ou autônomo
                    - Vagas com a escala 6x1
                    - Vagas presenciais ou híbridas fora de Curitiba
                    - Vagas que exigem faculdade
                    - Vagas que exigem 2 anos de experiência
                    - Vagas exclusivas para deficientes

                    3. PREFERÊNCIAS E BÔNUS (Aumentam a pontuação se tiver):
                    - Benefícios como vale transporte, Vale alimentação e/ou refeição, plano de saúde
                    - Foco em tarefas com Autocad e projetos ou planilhas
                    - Formato de trabalho híbrido ou 100% home office
                    - Salário acima de R$2.600
                    - Que não EXIJA muita experiência em Autocad 

                    4. INSTRUÇÕES DE SAÍDA OBRIGATÓRIAS:
                    Responda ESTRITAMENTE neste formato:
                    APROVADA: [SIM ou NÃO]
                    NOTA: [0 a 100, baseado nas preferências e bônus]
                    RESUMO: [1 frase curta justificando a aprovação ou reprovação]
               """,
    },
    {
        "nome": "Pamela - Tech",
        "ativo": False,  # Desativado temporariamente (mude para True quando quiser reativar)
        "webhook_url": (os.getenv("WEBHOOK_DEV") or os.getenv("WEHBOOK_DEV") or "").strip(),
        "incluir_fontes_tech": True,
        "localizacoes": ["Rio de Janeiro", "Brasil"],
        "termos_busca": [
            "Estágio Desenvolvimento",
            "Estágio Python",
            "Estágio Front-end",
            "Estágio Full Stack",
            "Estágio Dados IA",
            "Desenvolvedor Python Júnior",
            "Full Stack Júnior",
            "AI Engineer Júnior",
            "Analista de Sistemas Júnior",
            "Analista de Automação IA",
        ],
        "palavras_bloqueadas_titulo": [
            "sênior",
            "senior",
            "sr.",
            "sr ",
            "pleno",
            "tech lead",
            "especialista",
            "coordenador",
            "gerente",
            "diretor",
            "devops",
            "redes",
            "suporte técnico",
            "infraestrutura",
        ],
        "prompt_filtro": """
                     Você é um recrutador sênior. Avalie a vaga abaixo para o meu perfil.

                    1. VAGAS DESEJADAS
                      estágio de desenvolvimento, estágio frontend, estágio fullstack, estágio de backend, 
                      estágio de dados, estágio de IA e agentes, estagio de desenvolvimento de software, Estágio em Cloud
                      Full Stack Júnior, Analista de Sistemas Júnior, AI Engineer Júnior, Desenvolvedora Python Júnior, Prompt Engineer
                      NLP, Analista de Automação / IA, AI Solutions / AI Developer


                    2. REGRAS ELIMINATÓRIAS (Se violar QUALQUER uma, a vaga está reprovada):
                    - Vagas de Infraestrutura, Suporte, Redes ou DevOps.
                    - Vagas presenciais ou hibridas fora do Rio de Janeiro
                    - Vagas que o salário é abaixo de R$2.000 (Se o salário não estiver informado na descrição, NÃO elimine a vaga por este critério)
                    - Vagas Pj ou autônomo
                    - Vagas com a escala 6x1
                    - Vagas que exigem mais de 5 anos de experiência.
                    - Vagas exclusivas para deficientes
                    - Vagas de ESTÁGIO que não aceitem o encerramento da faculdade em julho de 2027

                    3. PREFERÊNCIAS E BÔNUS (Aumentam a pontuação se tiver):
                    - Trabalho 100% Remoto ou híbrido.
                    - Benefícios como Gympass, Auxílio Home Office, VR, VA, vale transporte.
                    - Foco em linguagens como Typescript e Python
                    - Salário acima ou igual a R$3.000

                    4. INSTRUÇÕES DE SAÍDA OBRIGATÓRIAS:
                    Responda ESTRITAMENTE neste formato:
                    APROVADA: [SIM ou NÃO]
                    NOTA: [0 a 100, baseado nas preferências e bônus]
                    RESUMO: [1 frase curta justificando a aprovação ou reprovação]
               """,
    },
]


# ==============================================================================
# GERENCIAMENTO DE HISTÓRICO (EVITA REPETIR VAGAS JÁ AVALIADAS)
# ==============================================================================
def carregar_historico() -> set[str]:
    """Carrega os IDs das vagas já avaliadas anteriormente."""
    if not os.path.exists(ARQUIVO_HISTORICO):
        return set()
    try:
        with open(ARQUIVO_HISTORICO, "r", encoding="utf-8") as f:
            dados = json.load(f)
            return set(dados.get("vagas_processadas", []))
    except Exception:
        return set()


def salvar_historico(vagas_processadas: set[str]) -> None:
    """Salva os IDs das vagas processadas (mantendo os últimos 2.000 registros)."""
    try:
        lista_recente = list(vagas_processadas)[-2000:]
        with open(ARQUIVO_HISTORICO, "w", encoding="utf-8") as f:
            json.dump({"vagas_processadas": lista_recente}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  [Aviso] Não foi possível salvar o histórico: {e}")


# ==============================================================================
# MONTAGEM DE PROMPTS E AVALIAÇÃO COM GEMINI AI
# ==============================================================================
def montar_prompt_vaga(instrucoes_perfil: str, vaga: dict) -> str:
    """Injeta os dados completos da vaga no prompt do perfil correspondente."""
    return (
        f"{instrucoes_perfil}\n\n"
        f"--- DADOS DA VAGA ---\n"
        f"Título: {vaga.get('titulo', '')}\n"
        f"Empresa: {vaga.get('empresa', 'Não informada')}\n"
        f"Local: {vaga.get('local', 'Não informado')}\n"
        f"Fonte: {vaga.get('fonte', 'Não informada')}\n"
        f"Salário: {vaga.get('salario', 'Não informado')}\n"
        f"Descrição: {vaga.get('descricao', '')}\n"
    )


def pre_filtrar_vaga(vaga: dict, perfil: dict) -> bool:
    """
    Faz uma triagem rápida pelo título antes de chamar a API da IA,
    descartando vagas claramente fora do nível (ex: Sênior, Gerente, Diretor).
    """
    titulo_lower = vaga.get("titulo", "").lower()
    bloqueadas = perfil.get("palavras_bloqueadas_titulo", [])
    for palavra in bloqueadas:
        if palavra.lower() in titulo_lower:
            return False
    return True


def interpretar_resposta_ia(texto_resposta: str) -> dict:
    """Extrai os campos APROVADA, NOTA e RESUMO da resposta estruturada do Gemini."""
    texto = (texto_resposta or "").strip()

    match_aprovada = re.search(r"APROVADA:\s*\[?(SIM|N[ÃA]O)\]?", texto, re.IGNORECASE)
    match_nota = re.search(r"NOTA:\s*\[?(\d{1,3})\]?", texto, re.IGNORECASE)
    match_resumo = re.search(r"RESUMO:\s*(.+)", texto, re.IGNORECASE)

    aprovada_str = match_aprovada.group(1).upper() if match_aprovada else "NÃO"
    aprovada = aprovada_str == "SIM"

    nota = int(match_nota.group(1)) if match_nota else 0
    nota = max(0, min(100, nota))

    resumo = match_resumo.group(1).strip().strip("[]") if match_resumo else texto[:250]

    return {
        "aprovada": aprovada,
        "nota": nota,
        "resumo": resumo,
        "bruto": texto,
    }


_modelo_validado = None


def avaliar_vaga_com_ia(prompt_completo: str) -> dict:
    """
    Envia o prompt para a API do Google Gemini com fallback automático de modelos
    e tratamento de limite de requisições (Rate Limit 429).
    """
    global _modelo_validado
    if not client:
        raise RuntimeError("A variável GOOGLE_KEY não foi configurada no arquivo .env!")

    if _modelo_validado:
        modelos_unicos = [_modelo_validado]
    else:
        modelos_tentativa = [
            MODELO_PREFERIDO,
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-3.8-flash",
        ]
        modelos_unicos = list(dict.fromkeys(modelos_tentativa))

    ultimo_erro = None
    for modelo in modelos_unicos:
        for tentativa in range(2):
            try:
                resultado = client.models.generate_content(
                    model=modelo,
                    contents=prompt_completo,
                )
                _modelo_validado = modelo
                return interpretar_resposta_ia(resultado.text)
            except Exception as e:
                erro_str = str(e)
                ultimo_erro = e
                # Se for erro de modelo inexistente (404/NOT_FOUND), tenta o próximo modelo da lista
                if "NOT_FOUND" in erro_str or "404" in erro_str or "not found" in erro_str.lower():
                    break
                # Se for Rate Limit (429 / RESOURCE_EXHAUSTED), aguarda alguns segundos e tenta de novo
                if "429" in erro_str or "RESOURCE_EXHAUSTED" in erro_str:
                    tempo_espera = 12 * (tentativa + 1)
                    print(f"  ⏳ Limite de requisições atingido no Gemini. Aguardando {tempo_espera}s...")
                    time.sleep(tempo_espera)
                    continue
                break

    print(f"  ❌ Erro ao consultar a IA do Gemini: {ultimo_erro}")
    return {
        "aprovada": False,
        "nota": 0,
        "resumo": f"Erro na avaliação: {ultimo_erro}",
        "bruto": "",
    }


def avaliar_lote_vagas_com_ia(instrucoes_perfil: str, lote_vagas: list[dict]) -> list[dict]:
    """
    Avalia até 10 vagas em UMA ÚNICA chamada da API do Gemini, economizando ~90% das
    requisições (RPM/RPD) e reduzindo drasticamente o consumo de tokens de entrada.
    Caso ocorra falha no parse do lote, faz fallback automático para avaliação individual.
    """
    global _modelo_validado
    if not client:
        raise RuntimeError("A variável GOOGLE_KEY não foi configurada no arquivo .env!")

    blocos_vagas = []
    for idx, vaga in enumerate(lote_vagas):
        blocos_vagas.append(
            f"=== VAGA #{idx} ===\n"
            f"Título: {vaga.get('titulo', '')}\n"
            f"Empresa: {vaga.get('empresa', 'Não informada')}\n"
            f"Local: {vaga.get('local', 'Não informado')}\n"
            f"Fonte: {vaga.get('fonte', 'Não informada')}\n"
            f"Salário: {vaga.get('salario', 'Não informado')}\n"
            f"Descrição: {vaga.get('descricao', '')[:1500]}"
        )

    texto_lote = "\n\n".join(blocos_vagas)
    prompt_lote = (
        f"{instrucoes_perfil}\n\n"
        f"ATENÇÃO: Avalie cada uma das {len(lote_vagas)} vagas abaixo separadamente seguindo as regras acima.\n"
        f"Retorne ESTRITAMENTE um array JSON válido contendo exatamente {len(lote_vagas)} objetos no formato:\n"
        f'[{{"indice": 0, "aprovada": true, "nota": 85, "resumo": "Justificativa curta em 1 frase"}}]\n\n'
        f"{texto_lote}"
    )

    modelos_unicos = (
        [_modelo_validado]
        if _modelo_validado
        else list(
            dict.fromkeys(
                [MODELO_PREFERIDO, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-3.8-flash"]
            )
        )
    )

    for modelo in modelos_unicos:
        for tentativa in range(2):
            try:
                resultado = client.models.generate_content(
                    model=modelo,
                    contents=prompt_lote,
                    config={"response_mime_type": "application/json"},
                )
                _modelo_validado = modelo
                dados_json = json.loads(resultado.text)
                if isinstance(dados_json, list):
                    mapa_por_indice = {
                        int(item.get("indice", i)): item for i, item in enumerate(dados_json) if isinstance(item, dict)
                    }
                    respostas_lote = []
                    for i in range(len(lote_vagas)):
                        item = mapa_por_indice.get(i, {})
                        aprovada_val = item.get("aprovada", False)
                        if isinstance(aprovada_val, str):
                            aprovada_val = aprovada_val.strip().upper() in ("SIM", "TRUE", "1")
                        nota_val = int(item.get("nota", 0) or 0)
                        resumo_val = str(item.get("resumo", "Sem justificativa.")).strip()
                        respostas_lote.append(
                            {
                                "aprovada": bool(aprovada_val),
                                "nota": max(0, min(100, nota_val)),
                                "resumo": resumo_val,
                                "bruto": json.dumps(item, ensure_ascii=False),
                            }
                        )
                    return respostas_lote
            except Exception as e:
                erro_str = str(e)
                if "NOT_FOUND" in erro_str or "404" in erro_str or "not found" in erro_str.lower():
                    break
                if "429" in erro_str or "RESOURCE_EXHAUSTED" in erro_str:
                    tempo_espera = 12 * (tentativa + 1)
                    print(f"  ⏳ Limite de requisições atingido no Gemini. Aguardando {tempo_espera}s...")
                    time.sleep(tempo_espera)
                    continue
                break

    # Fallback: se o lote falhar por qualquer motivo, avalia individualmente
    return [avaliar_vaga_com_ia(montar_prompt_vaga(instrucoes_perfil, v)) for v in lote_vagas]


# ==============================================================================
# ENVIO DE NOTIFICAÇÕES RICAS PARA O DISCORD (WEBHOOK EMBEDS)
# ==============================================================================
def enviar_notificacao_discord(perfil: dict, vaga: dict, avaliacao: dict) -> bool:
    """Envia um Embed formatado para o canal do Discord configurado no perfil."""
    webhook_url = perfil.get("webhook_url", "")
    if not webhook_url or not webhook_url.startswith("http"):
        print(f"  ⚠️ Webhook não configurado ou inválido para o perfil '{perfil['nome']}'.")
        return False

    nota = avaliacao.get("nota", 0)
    # Define a cor lateral do Embed conforme a nota (Verde >= 80, Azul >= 60, Amarelo < 60)
    if nota >= 80:
        cor_embed = 0x2ECC71  # Verde
    elif nota >= 60:
        cor_embed = 0x3498DB  # Azul
    else:
        cor_embed = 0xF1C40F  # Amarelo

    payload = {
        "username": "AI Job Notifier 🤖",
        "embeds": [
            {
                "title": f"🎯 {vaga['titulo'][:240]}",
                "url": vaga.get("link") or "https://www.google.com",
                "color": cor_embed,
                "description": f"** parecer da IA:**\n> {avaliacao.get('resumo', 'Vaga compatível com o perfil.')}",
                "fields": [
                    {
                        "name": "🏢 Empresa",
                        "value": vaga.get("empresa", "Não informada")[:100],
                        "inline": True,
                    },
                    {
                        "name": "📍 Local / Modelo",
                        "value": vaga.get("local", "Não informado")[:100],
                        "inline": True,
                    },
                    {
                        "name": "🌐 Plataforma",
                        "value": vaga.get("fonte", "Web")[:100],
                        "inline": True,
                    },
                    {
                        "name": "⭐ Nota de Match",
                        "value": f"**{nota}/100**",
                        "inline": True,
                    },
                    {
                        "name": "👤 Perfil",
                        "value": perfil["nome"],
                        "inline": True,
                    },
                    {
                        "name": "🔗 Candidatura",
                        "value": f"[Clique aqui para abrir a vaga]({vaga.get('link', '')})",
                        "inline": True,
                    },
                ],
                "footer": {
                    "text": f"Filtrado por Google Gemini AI • Fonte: {vaga.get('fonte', 'Web')}"
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ],
    }

    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code in (200, 204):
            return True
        print(f"  ⚠️ Falha ao enviar para o Discord (Status {resp.status_code}): {resp.text}")
    except Exception as e:
        print(f"  ❌ Erro de conexão com o Webhook do Discord: {e}")

    return False


# ==============================================================================
# EXECUÇÃO PRINCIPAL DO PIPELINE
# ==============================================================================
def executar_pipeline() -> None:
    """Executa o fluxo completo: Raspagem -> Filtragem IA -> Notificação Discord."""
    print("=" * 70)
    print("🚀 INICIANDO AI-POWERED JOB SCRAPER & NOTIFIER")
    print("=" * 70)

    historico = carregar_historico()
    total_aprovadas_geral = 0

    for perfil in perfis_busca:
        nome_perfil = perfil["nome"]
        if not perfil.get("ativo", True):
            print(f"\n⏸️ Perfil '{nome_perfil}' está desativado no momento. Pulando...")
            continue

        print(f"\n📌 Processando perfil: {nome_perfil}")
        print("-" * 70)

        vagas_encontradas = buscar_vagas(
            termos_busca=perfil["termos_busca"],
            localizacoes=perfil["localizacoes"],
            incluir_fontes_tech=perfil.get("incluir_fontes_tech", True),
            limite_por_fonte=5,
        )

        # Filtra vagas inéditas para este perfil e aplica pré-filtro rápido de título
        vagas_candidatas = []
        for vaga in vagas_encontradas:
            chave_historico = f"{nome_perfil}:{vaga['id']}"
            if chave_historico in historico:
                continue
            if not pre_filtrar_vaga(vaga, perfil):
                historico.add(chave_historico)
                continue
            vagas_candidatas.append(vaga)

        print(
            f"📋 {len(vagas_candidatas)} vaga(s) inédita(s) pronta(s) para avaliação da IA "
            f"(limitado a {LIMITE_AVALIACOES_IA_POR_PERFIL} por execução)."
        )

        aprovadas_perfil = 0
        vagas_para_avaliar = vagas_candidatas[:LIMITE_AVALIACOES_IA_POR_PERFIL]

        for inicio in range(0, len(vagas_para_avaliar), TAMANHO_LOTE_IA):
            lote = vagas_para_avaliar[inicio : inicio + TAMANHO_LOTE_IA]
            fim = inicio + len(lote)
            print(
                f"\n  🧠 Avaliando lote de vagas [{inicio + 1} a {fim} de {len(vagas_para_avaliar)}] "
                f"em 1 única requisição ao Gemini..."
            )

            avaliacoes = avaliar_lote_vagas_com_ia(perfil["prompt_filtro"], lote)

            for idx_lote, (vaga, avaliacao) in enumerate(zip(lote, avaliacoes), start=inicio + 1):
                chave_historico = f"{nome_perfil}:{vaga['id']}"
                if avaliacao.get("bruto"):
                    historico.add(chave_historico)

                if avaliacao["aprovada"]:
                    aprovadas_perfil += 1
                    total_aprovadas_geral += 1
                    print(
                        f"    [{idx_lote}] ✅ APROVADA! [{vaga['fonte']}] {vaga['titulo']} "
                        f"(Nota: {avaliacao['nota']}/100) -> {avaliacao['resumo']}"
                    )
                    enviado = enviar_notificacao_discord(perfil, vaga, avaliacao)
                    if enviado:
                        print("        📨 Notificação enviada para o Discord com sucesso!")
                else:
                    print(
                        f"    [{idx_lote}] ❌ Reprovada [{vaga['fonte']}] {vaga['titulo']} "
                        f"(Nota: {avaliacao['nota']}/100) -> {avaliacao['resumo']}"
                    )

            salvar_historico(historico)
            time.sleep(2)
        print(f"🏁 Fim do perfil '{nome_perfil}': {aprovadas_perfil} vaga(s) aprovada(s) e enviada(s)!")

    print("\n" + "=" * 70)
    print(f"🎉 VARREDURA DIÁRIA CONCLUÍDA! Total de vagas enviadas ao Discord: {total_aprovadas_geral}")
    print("=" * 70)


if __name__ == "__main__":
    import sys

    # Se rodar com "--diario" (ou LOOP_DIARIO=true no .env), mantém o script ativo
    # executando para ambos os perfis 1 vez a cada 24 horas (86.400 segundos).
    modo_loop_diario = "--diario" in sys.argv or os.getenv("LOOP_DIARIO", "").lower() == "true"

    if modo_loop_diario:
        while True:
            executar_pipeline()
            print("\n⏰ Próxima busca para ambos os perfis agendada para daqui a 24 horas (1x ao dia)...")
            time.sleep(24 * 60 * 60)
    else:
        executar_pipeline()
