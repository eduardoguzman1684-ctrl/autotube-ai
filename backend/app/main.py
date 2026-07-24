
from pipeline.video_pipeline import VideoPipeline


def main():

    print("🤖 AutoTube AI iniciado")
    print("------------------------")

    topic = input("Escribe el tema del video: ")

    pipeline = VideoPipeline()

    video = pipeline.run(topic)

    print("\n==============================")
    print("🎉 PROCESO COMPLETADO")
    print("==============================")
    print(f"📹 Video generado: {video}")


if __name__ == "__main__":
    main()