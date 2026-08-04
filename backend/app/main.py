from pipeline.video_pipeline import VideoPipeline
from trends.youtube_trends import mejor_tema
from research.gemini_research import investigar_tema
from youtube.youtube_uploader import upload_autotube_video

import traceback


def main():

    print("🤖 AutoTube AI iniciado")
    print("------------------------")


    # ===============================
    # SELECCIONAR TEMA
    # ===============================

    tendencia = mejor_tema()

    topic = tendencia["titulo"]

    print("\n🔥 Tema seleccionado automáticamente:")
    print(topic)



    # ===============================
    # INVESTIGACIÓN GEMINI
    # ===============================

    print("\n🔍 Investigando tema con Gemini...")


    try:

        investigacion = investigar_tema(topic)


        print("\n==============================")
        print("📚 INVESTIGACIÓN GEMINI")
        print("==============================")

        print(investigacion)


    except Exception as e:

        print("\n❌ ERROR GEMINI")

        print(type(e).__name__)
        print(e)

        traceback.print_exc()

        investigacion = topic



    # ===============================
    # CREAR VIDEO
    # ===============================


    pipeline = VideoPipeline()


    video = pipeline.run(investigacion)



    print("\n==============================")
    print("🎬 VIDEO GENERADO")
    print("==============================")

    print(video)



    # ===============================
    # SUBIR A YOUTUBE
    # ===============================


    print("\n🚀 Subiendo video a YouTube...")


    try:


        url = upload_autotube_video(

            title=topic,


            description=f"""
{investigacion}


🎬 Video creado automáticamente con AutoTube AI.

Generado con:
- Gemini AI
- Inteligencia Artificial
- Automatización Python

#AI #Documentary #Technology #AutoTubeAI
""",


            tags=[

                "AI",
                "Documentary",
                "History",
                "Technology",
                "AutoTube AI",
                "Gemini",
                "Artificial Intelligence"

            ],


            privacy="private"

        )


        print("\n==============================")
        print("🎉 VIDEO PUBLICADO")
        print("==============================")


        print("🔗 URL DEL VIDEO:")
        print(url)



    except Exception as e:


        print("\n❌ ERROR SUBIENDO A YOUTUBE")

        print(type(e).__name__)
        print(e)

        traceback.print_exc()



    print("\n==============================")
    print("✅ PROCESO COMPLETADO")
    print("==============================")


    print(f"📹 Archivo local:")
    print(video)



if __name__ == "__main__":

    main()