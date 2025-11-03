# README

como configurar e rodar o projeto

## 1. Configuração do Ambiente

1.  abra dois terminal na pasta raiz
2.  crie e ative um venv
3.  Instale as dependências



   
## 2. Banco de Dados

o projeto usa SQLite, O arquivo `quiz.db` será criado(ou atualizado caso ja tenha sido criado) automaticamente na pasta raiz quando você iniciar a api, as tabelas (`personality_users` e `personality_responses`) também são criadas automaticamente


## 3. Rodando os Servidores

### Terminal 1: Rodar a API (Backend)

1.  Ative o ambiente virtual
2.  Inicie o servidor da API com Uvicorn:
    ```bash
    uvicorn app.main:app --reload
    ```
3.  Deixe este terminal rodando, a api vai ta disponível em `http://127.0.0.1:8000`

### Terminal 2: Rodar o Site

1. Rodar o front
    ```bash
    python -m http.server 8080
    ```

## 4. Como Usar

1.  Com os 2 terminais rodando, entrar no quiz
    **`http://127.0.0.1:8080/quiz.html`**

2.  Responda todas as perguntas e clique em ver resultados


### Endpoints de Teste (Admin)

Para checar a qualidade e a confiabilidade das perguntas de cada eixo, você pode acessar os endpoints de estatística no navegador

* `http://127.0.0.1:8000/admin/stats/WEB_DEV`
* `http://127.0.0.1:8000/admin/stats/DATA_SCIENCE`
* `http://127.0.0.1:8000/admin/stats/CYBERSECURITY`


##FILE STRUCTURE

TCC/

├── app/                   
│   ├── __init__.py        
│   ├── database.py       
│   ├── main.py           
│   ├── models.py         
│   ├── personality_scoring.py  
│   └── seed_db.py        
│
├── quiz.db                 
├── quiz.html              
└── requirements.txt        
