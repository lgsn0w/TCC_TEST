from .database import SessionLocal, engine
from .models import ContentResource, Base

RESOURCES = [
    # Web Dev
    {"title": "MDN Web Docs: Guia para Iniciantes", "url": "https://developer.mozilla.org/pt-BR/docs/Learn", "type": "documentação", "career_axis": "WEB_DEV"},
    {"title": "O que é HTML, CSS e JavaScript?", "url": "https://www.youtube.com/watch?v=gSg-tXtK7sY", "type": "vídeo", "career_axis": "WEB_DEV"},
    {"title": "Curso de React.js para Iniciantes", "url": "https://www.youtube.com/watch?v=FXqX7oof0I4", "type": "curso", "career_axis": "WEB_DEV"},
    {"title": "CSS-Tricks: Um Guia para Flexbox", "url": "https://css-tricks.com/snippets/css/a-guide-to-flexbox/", "type": "artigo", "career_axis": "WEB_DEV"},

    # Data Science
    {"title": "O que é Ciência de Dados? (Simplificado)", "url": "https://www.youtube.com/watch?v=F3s_42O3LdI", "type": "vídeo", "career_axis": "DATA_SCIENCE"},
    {"title": "Pandas: Análise de Dados em Python", "url": "https://pandas.pydata.org/docs/user_guide/10min.html", "type": "documentação", "career_axis": "DATA_SCIENCE"},
    {"title": "Scikit-Learn: Machine Learning em Python", "url": "https://scikit-learn.org/stable/tutorial/basic/tutorial.html", "type": "tutorial", "career_axis": "DATA_SCIENCE"},
    {"title": "Kaggle: Competições de Data Science", "url": "https://www.kaggle.com/", "type": "plataforma", "career_axis": "DATA_SCIENCE"},

    # Cybersecurity
    {"title": "O que é Cibersegurança?", "url": "https://www.youtube.com/watch?v=sYvni-cAMt0", "type": "vídeo", "career_axis": "CYBERSECURITY"},
    {"title": "TryHackMe: Aprenda Cibersegurança Jogando", "url": "https://tryhackMe.com/", "type": "plataforma", "career_axis": "CYBERSECURITY"},
    {"title": "OWASP Top 10: As Maiores Vulnerabilidades Web", "url": "https://owasp.org/www-project-top-ten/", "type": "artigo", "career_axis": "CYBERSECURITY"},
]

def seed_data():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        count = db.query(ContentResource).count()
        if count > 0:
            print(f"O banco de dados já contém {count} recursos. O script 'seed' não será executado novamente.")
            print("Para re-popular o banco, delete o arquivo 'quiz.db' primeiro.")
            return

        for res in RESOURCES:
            db_resource = ContentResource(
                title=res["title"],
                url=res["url"],
                type=res["type"],
                career_axis=res["career_axis"]
            )
            db.add(db_resource)

        db.commit()
        print(f"Sucesso! {len(RESOURCES)} recursos foram adicionados ao banco de dados.")

    except Exception as e:
        print(f"Erro ao popular o banco de dados: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
