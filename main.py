import requests 

WEBHOOK_URL = "https://discord.com/api/webhooks/1556088710293098558/hnKhvZ1iZSqU1pyeLyHXswRn2jkhbk-hlnsjzJlu1QAzdqKznVOBfECkny_DlXI1ZJAI"

perfis_busca = [
     {
          "nome": "Pamela - Tech",
          "webhook_url": "https://discord.com/api/webhooks/1556088437680119918/FVZb_6IKK44xtbyFUwfjQfdf-ArD-Xx2jEsnpJq7oIAAq8YgJhFQnXgfwGFUcgwY83F7",
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
               """
     },
     {
          "nome": "Nycollas - Edificações",
          "webhook_url": "https://discord.com/api/webhooks/1556088710293098558/hnKhvZ1iZSqU1pyeLyHXswRn2jkhbk-hlnsjzJlu1QAzdqKznVOBfECkny_DlXI1ZJAI",
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
               """
     }
]

# if "APROVADA: SIM" in resposta_ia:

payload = { # pacote que vamos enviar para o discord
     "content": "Meu pau na sua mão",
     "embeds": [ # cartões organizados 
          {
               "title": " kkkk zueira te amo",
               "description": "Love u",
               "color": 5814783
          }
     ]
}

resposta = requests.post(WEBHOOK_URL, json=payload) # recebimento

print(f"Código de resposta do Discord: {resposta.status_code}") # injetar variaveis no texto
