import os
import requests
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv


load_dotenv()


API_KEY = os.getenv("PIXABAY_API_KEY")



def prepare_image_folder():

    if not os.path.exists("images"):
        os.makedirs("images")



def create_scene_images(scenes):

    prepare_image_folder()

    images = []


    for scene in scenes:

        filename = f"images/escena_{scene['escena']}.jpg"


        print("\n🖼️ Buscando imagen para escena:")
        print(scene["titulo"])



        palabras = scene["descripcion"][:100]



        params = {

            "key": API_KEY,

            "q": palabras,

            "image_type": "photo",

            "orientation": "horizontal",

            "per_page": 5

        }



        try:

            response = requests.get(

                "https://pixabay.com/api/",

                params=params,

                timeout=30

            )


            data = response.json()



            if len(data["hits"]) == 0:

                print("❌ No hay imágenes")

                continue



            image_url = data["hits"][0]["largeImageURL"]



            img_data = requests.get(

                image_url,

                timeout=30

            ).content



            img = Image.open(

                BytesIO(img_data)

            )


            img = img.convert("RGB")


            img.save(

                filename,

                "JPEG",

                quality=95

            )



            images.append(filename)


            print(

                "✅ Imagen creada:",

                filename

            )



        except Exception as e:

            print(

                "❌ Error:",

                e

            )



    return images