import requests
from bs4 import BeautifulSoup

def buscar_vagas(): 
     print("Iniciando raspagem...")
     url = "https://pythonjobs.github.io/"

     site = requests.get(url) # baixa pagina inteira
     sopa = BeautifulSoup(site.text, 'html.parser') # transforma o HTML bagunçado
     lista_vagas = sopa.find_all('div', class_='job')

     print(f"Encontramos {len(lista_vagas)} vagas na página!") 

     vagas_limpas = []

     for vaga in lista_vagas: 
          titulo = vaga.find('h1').text
          descricao = vaga.find('p').text

          vaga_formatada = {
               'titulo': titulo,
               'descricao': descricao,
          }
          
          vagas_limpas.append(vaga_formatada)

     return vagas_limpas
