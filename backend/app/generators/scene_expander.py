import logging


logger = logging.getLogger(
    "AutoTubeAI"
)


# =====================================
# AUTOTUBE AI
# EXPANSOR DE ESCENAS DOCUMENTALES
# XTTS READY
# =====================================


def expandir_escenas(documental):


    titulo = documental.get(
        "titulo",
        "Historia desconocida"
    )


    escenas = [

        {
            "numero": 1,
            "titulo": "Introducción histórica",
            "narracion":
            f"Durante siglos, {titulo} ha despertado la curiosidad de historiadores y arqueólogos. "
            "Su historia revela una civilización llena de misterios, avances y acontecimientos "
            "que cambiaron el desarrollo del mundo antiguo."
        },


        {
            "numero": 2,
            "titulo": "Ubicación geográfica",
            "narracion":
            f"{titulo} se desarrolló en una región estratégica que permitió el intercambio "
            "cultural y comercial con otros pueblos. Su ubicación fue clave para su crecimiento "
            "y expansión."
        },


        {
            "numero": 3,
            "titulo": "Origen de la civilización",
            "narracion":
            "Los primeros grupos humanos que formaron esta civilización comenzaron creando "
            "asentamientos organizados que con el tiempo evolucionaron hasta convertirse "
            "en un poderoso reino."
        },


        {
            "numero": 4,
            "titulo": "Primeros asentamientos",
            "narracion":
            "Las primeras ciudades fueron centros donde surgieron nuevas formas de organización "
            "social, producción agrícola y desarrollo cultural."
        },


        {
            "numero": 5,
            "titulo": "Formación del reino",
            "narracion":
            "Con el paso del tiempo, sus líderes lograron unir diferentes territorios formando "
            "una estructura política más fuerte y organizada."
        },


        {
            "numero": 6,
            "titulo": "Gobernantes importantes",
            "narracion":
            "Sus gobernantes tuvieron un papel fundamental en la expansión territorial, "
            "la administración del reino y las decisiones militares."
        },


        {
            "numero": 7,
            "titulo": "Ejército y conquistas",
            "narracion":
            "El poder militar permitió defender sus fronteras y participar en importantes "
            "conflictos que marcaron su época."
        },


        {
            "numero": 8,
            "titulo": "Arquitectura y ciudades",
            "narracion":
            "Sus construcciones muestran el nivel de conocimiento alcanzado en ingeniería, "
            "planificación urbana y arquitectura."
        },


        {
            "numero": 9,
            "titulo": "Cultura y escritura",
            "narracion":
            "La escritura permitió conservar leyes, tratados y acontecimientos importantes, "
            "dejando información valiosa para las generaciones futuras."
        },


        {
            "numero": 10,
            "titulo": "Religión y tradiciones",
            "narracion":
            "Sus creencias religiosas formaban parte fundamental de la vida cotidiana "
            "y estaban relacionadas con sus costumbres y tradiciones."
        },


        {
            "numero": 11,
            "titulo": "Relaciones internacionales",
            "narracion":
            "Esta civilización estableció alianzas y conflictos con otros grandes pueblos "
            "de su época mediante acuerdos diplomáticos y guerras."
        },


        {
            "numero": 12,
            "titulo": "Grandes batallas",
            "narracion":
            "Las batallas más importantes demostraron sus estrategias militares "
            "y tuvieron consecuencias que cambiaron el equilibrio de poder."
        },


        {
            "numero": 13,
            "titulo": "Economía y comercio",
            "narracion":
            "Su economía dependía de la agricultura, los recursos naturales y las rutas "
            "comerciales que conectaban diferentes regiones."
        },


        {
            "numero": 14,
            "titulo": "Caída del imperio",
            "narracion":
            "Como muchas civilizaciones antiguas, enfrentó problemas internos, conflictos "
            "y amenazas externas que provocaron su desaparición."
        },


        {
            "numero": 15,
            "titulo": "Descubrimientos arqueológicos",
            "narracion":
            "Los descubrimientos realizados por arqueólogos permitieron recuperar documentos, "
            "objetos y conocimientos sobre esta antigua civilización."
        },


        {
            "numero": 16,
            "titulo": "Legado histórico",
            "narracion":
            "Su legado continúa siendo estudiado porque aporta conocimientos importantes "
            "sobre la evolución política, cultural y tecnológica de la humanidad."
        }

    ]


    # Añadir información para imágenes

    for escena in escenas:

        escena["imagen_prompt"] = (
            f"{titulo}, {escena['titulo']}, "
            "documental histórico cinematográfico, "
            "realista, alta calidad, iluminación dramática"
        )


        # compatibilidad XTTS

        escena["texto"] = escena["narracion"]



    logger.info(
        f"Escenas generadas: {len(escenas)}"
    )


    return escenas