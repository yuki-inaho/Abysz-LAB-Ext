import gradio as gr
import subprocess
import os
import imageio
import numpy as np
from gradio.outputs import Image
from PIL import Image
import sys
import cv2
import shutil
import time
import math

from modules import shared
from modules import scripts
from modules import script_callbacks


class Script(scripts.Script):
    def title(self):
        return "Abysz LAB"

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def ui(self, is_img2img):
        return []


def main(
    ruta_entrada_1,
    ruta_entrada_2,
    ruta_salida,
    denoise_blur,
    dfi_strength,
    dfi_deghost,
    inter_denoise,
    inter_denoise_size,
    inter_denoise_speed,
    fine_blur,
    frame_refresh_frequency,
    refresh_strength,
    smooth,
    frames_limit,
    ruta_entrada_3,
    ruta_salida_1,
    ddf_strength,
    over_strength,
    norm_strength,
    ruta_entrada_4,
    ruta_entrada_5,
    ruta_salida_2,
    fuse_strength,
    ruta_entrada_6,
    ruta_salida_3,
    fps_count,
):
    # Define the paths to the folders
    maskD = os.path.join(os.getcwd(), "extensions", "Abysz-LAB-Ext", "scripts", "Run", "MaskD")
    maskS = os.path.join(os.getcwd(), "extensions", "Abysz-LAB-Ext", "scripts", "Run", "MaskS")
    source = os.path.join(os.getcwd(), "extensions", "Abysz-LAB-Ext", "scripts", "Run", "Source")

    # Check if the folders exist and delete them if they do
    folders_to_check = [source, maskS, maskD]
    for folder in folders_to_check:
        if os.path.exists(folder):
            shutil.rmtree(folder)

    # Create the folders
    folders_to_create = [source, maskS, ruta_salida, maskD]
    for folder in folders_to_create:
        os.makedirs(folder, exist_ok=True)

    # Copy the images from the specified directory to the Source folder in JPEG quality 100
    # @TODO: check "output_dir"
    def copy_images(input_dir, output_dir, frames_limit=0):
        count = 0  # initialize a counter to keep track of the number of images copied

        files = os.listdir(input_dir)
        sorted_files = sorted(files)

        # Loop through all the files in the input directory
        for i, file in enumerate(sorted_files):
            if file.endswith(".jpg") or file.endswith(".jpeg") or file.endswith(".png"):
                img = Image.open(os.path.join(input_dir, file))
                rgb_img = img.convert("RGB")
                rgb_img.save(os.path.join("./extensions/Abysz-LAB-Ext/scripts/Run/Source", "{:04d}.jpeg".format(i + 1)), "jpeg", quality=100)
                count += 1
            if frames_limit > 0 and count >= frames_limit:
                break

    # Call the function copy_images to copy the images
    copy_images(ruta_entrada_1, ruta_salida, frames_limit)

    # Folder where the images from Gen are located
    def sresize(gen_folder_path):
        """Resize images in the FULL folder to match the resolution of the Gen image."""

        # Folder where the images from Gen are located
        gen_folder = gen_folder_path

        # Folder where the FULL images are located
        full_folder = "./extensions/Abysz-LAB-Ext/scripts/Run/Source"

        # Get the aspect ratio of the Gen image
        gen_images = os.listdir(gen_folder)
        gen_image_path = os.path.join(gen_folder, gen_images[0])
        gen_image = cv2.imread(gen_image_path)
        gen_height, gen_width = gen_image.shape[:2]
        gen_aspect_ratio = gen_width / gen_height

        # Loop through all the images in the FULL folder
        for image_name in sorted(os.listdir(full_folder)):
            image_path = os.path.join(full_folder, image_name)
            image = cv2.imread(image_path)
            height, width = image.shape[:2]
            aspect_ratio = width / height

            # Crop or pad the FULL image to match the aspect ratio of the Gen image
            if aspect_ratio != gen_aspect_ratio:
                if aspect_ratio > gen_aspect_ratio:
                    # The image is wider than the Gen image
                    crop_width = int(height * gen_aspect_ratio)
                    x = int((width - crop_width) / 2)
                    image = image[:, x : x + crop_width]
                else:
                    # The image is taller than the Gen image
                    crop_height = int(width / gen_aspect_ratio)
                    y = int((height - crop_height) / 2)
                    image = image[y : y + crop_height, :]

            # Resize the FULL image to match the resolution of the Gen image
            image = cv2.resize(image, (gen_width, gen_height))

            # Save the resized image in the FULL folder
            cv2.imwrite(os.path.join(full_folder, image_name), image)

    # Call the sresize function to resize the FULL images
    sresize(ruta_entrada_2)

    def s_g_rename(ruta_entrada_2):
        # Set path of the "Source" folder
        gen_dir = ruta_entrada_2

        # Get a list of file names in the "Source" folder and sort it alphabetically
        files2 = sorted(os.listdir(gen_dir))

        # Rename each file with a suffix "rename"
        for i, file_name in enumerate(files2):
            old_path = os.path.join(gen_dir, file_name)
            new_file_name = f"{i+1:04d}rename"
            new_path = os.path.join(gen_dir, new_file_name + os.path.splitext(file_name)[1])
            try:
                os.rename(old_path, new_path)
            except FileExistsError:
                print(f"The file {new_file_name} already exists. Rename is skipped.")

        # Get a list of file names in the "Source" folder again
        files2 = sorted(os.listdir(gen_dir))

        # Remove the "rename" suffix from the file names
        for i, file_name in enumerate(files2):
            old_path = os.path.join(gen_dir, file_name)
            new_file_name = f"{i+1:04d}"
            new_path = os.path.join(gen_dir, new_file_name + os.path.splitext(file_name)[1])
            try:
                os.rename(old_path, new_path)
            except FileExistsError:
                print(f"The file {new_file_name} already exists. Rename is skipped.")

    s_g_rename(ruta_entrada_2)

    # Get the first file in the ruta_entrada_2 folder
    gen_files = os.listdir(ruta_entrada_2)
    if gen_files:
        first_gen_file = gen_files[0]

        # Copy the file to the "Output" folder and replace if it already exists
        output_file = os.path.join(ruta_salida, first_gen_file)
        shutil.copyfile(os.path.join(ruta_entrada_2, first_gen_file), output_file)

    # Subprocess call
    def denoise(denoise_blur):
        if denoise_blur < 1:  # Condition 1: strength must be greater than 1
            return

        denoise_kernel = denoise_blur
        # Get the list of file names in the Source folder
        files = os.listdir("./extensions/Abysz-LAB-Ext/scripts/Run/Source")

        # Loop through each file in the Source folder
        for file in files:
            # Read the image with OpenCV
            img = cv2.imread(os.path.join("./extensions/Abysz-LAB-Ext/scripts/Run/Source", file))

            # Apply the blur filter with a 5x5 kernel size
            dst = cv2.bilateralFilter(img, denoise_kernel, 31, 31)

            # Save the resulting image in the Source folder with the same name
            cv2.imwrite(os.path.join("./extensions/Abysz-LAB-Ext/scripts/Run/Source", file), dst)

    denoise(denoise_blur)

    # Definir la carpeta donde están los archivos
    carpeta = "./extensions/Abysz-LAB-Ext/scripts/Run/Source"

    # Crear la carpeta MaskD si no existe
    os.makedirs("./extensions/Abysz-LAB-Ext/scripts/Run/MaskD", exist_ok=True)

    # Inicializar contador
    contador = 1

    umbral_size = dfi_strength
    # Iterar a través de los archivos de imagen en la carpeta Source
    for filename in sorted(os.listdir(carpeta)):
        # Cargar la imagen actual y la siguiente en escala de grises
        if contador > 1:
            siguiente = cv2.imread(os.path.join(carpeta, filename), cv2.IMREAD_GRAYSCALE)
            diff = cv2.absdiff(anterior, siguiente)

            # Aplicar un umbral y guardar la imagen resultante en la carpeta MaskD. Menos es más.
            umbral = umbral_size
            umbralizado = cv2.threshold(diff, umbral, 255, cv2.THRESH_BINARY_INV)[1]  # Invertir los colores
            cv2.imwrite(os.path.join("./extensions/Abysz-LAB-Ext/scripts/Run/MaskD", f"{contador-1:04d}.png"), umbralizado)

        anterior = cv2.imread(os.path.join(carpeta, filename), cv2.IMREAD_GRAYSCALE)
        contador += 1

        # Actualmente, el tipo de umbralización es cv2.THRESH_BINARY_INV, que invierte los colores de la imagen umbralizada.
        # Puedes cambiarlo a otro tipo de umbralización,
        # como cv2.THRESH_BINARY, cv2.THRESH_TRUNC, cv2.THRESH_TOZERO o cv2.THRESH_TOZERO_INV.

    # Obtener la lista de los nombres de los archivos en la carpeta MaskD
    files = os.listdir("./extensions/Abysz-LAB-Ext/scripts/Run/MaskD")
    # Definir la carpeta donde están los archivos
    carpeta = "./extensions/Abysz-LAB-Ext/scripts/Run/MaskD"
    blur_kernel = smooth

    # Iterar sobre cada archivo
    for file in files:
        if dfi_deghost == 0:
            continue
        # Leer la imagen de la carpeta MaskD
        # img = cv2.imread("MaskD" + file)
        img = cv2.imread(os.path.join("./extensions/Abysz-LAB-Ext/scripts/Run/MaskD", file))

        # Invertir la imagen usando la función bitwise_not()
        img_inv = cv2.bitwise_not(img)

        kernel_size = dfi_deghost

        # Dilatar la imagen usando la función dilate()
        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (kernel_size, kernel_size)
        )  # Puedes cambiar el tamaño y la forma del kernel según tus preferencias
        img_dil = cv2.dilate(img_inv, kernel)

        # Volver a invertir la imagen usando la función bitwise_not()
        img_out = cv2.bitwise_not(img_dil)

        # Sobrescribir la imagen en la carpeta MaskD con el mismo nombre que el original
        # cv2.imwrite("MaskD" + file, img_out)
        # cv2.imwrite(os.path.join("MaskD", file, img_out))
        filename = os.path.join("./extensions/Abysz-LAB-Ext/scripts/Run/MaskD", file)
        cv2.imwrite(filename, img_out)

    # Iterar a través de los archivos de imagen en la carpeta MaskD
    if smooth > 1:
        for imagen in os.listdir(carpeta):
            if imagen.endswith(".jpg") or imagen.endswith(".png") or imagen.endswith(".jpeg"):
                # Leer la imagen
                img = cv2.imread(os.path.join(carpeta, imagen))
                # Aplicar el filtro
                img = cv2.GaussianBlur(img, (blur_kernel, blur_kernel), 0)
                # Guardar la imagen con el mismo nombre
                cv2.imwrite(os.path.join(carpeta, imagen), img)

    # INICIO DEL BATCH Obtener el nombre del archivo en MaskD sin ninguna extensión
    # Agregar una variable de contador de bucles
    loop_count = 0

    # Agregar un bucle while para ejecutar el código en bucle infinito
    while True:
        mask_files = sorted(os.listdir(maskD))
        if not mask_files:
            print(f"No frames left")
            # Eliminar las carpetas Source, MaskS y MaskD si no hay más archivos para procesar
            shutil.rmtree(maskD)
            shutil.rmtree(maskS)
            shutil.rmtree(source)
            break

        extra_mod = fine_blur

        mask = mask_files[0]
        maskname = os.path.splitext(mask)[0]

        maskp_path = os.path.join(maskD, mask)

        img = cv2.imread(maskp_path, cv2.IMREAD_GRAYSCALE)  # leer la imagen en escala de grises
        n_white_pix = np.sum(img == 255)  # contar los píxeles que son iguales a 255 (blanco)
        total_pix = img.size  # obtener el número total de píxeles en la imagen
        percentage = (n_white_pix / total_pix) * 100  # calcular el porcentaje de píxeles blancos
        percentage = round(percentage, 1)  # redondear el porcentaje a 1 decimal

        # calcular la variable extra
        extra = 100 - percentage  # restar el porcentaje a 100
        extra = extra / 3  # dividir el resultado por 3
        extra = math.ceil(extra)  # redondear hacia arriba al entero más cercano
        if extra % 2 == 0:  # verificar si el número es par
            extra = extra + 1  # sumarle 1 para hacerlo impar

        # Dynamic Blur
        imgb = cv2.imread(maskp_path)  # leer la imagen con opencv
        img_blur = cv2.GaussianBlur(imgb, (extra, extra), 0)

        # guardar la imagen modificada con el mismo nombre y ruta
        cv2.imwrite(maskp_path, img_blur)

        # Obtener la ruta de la imagen en la subcarpeta de output que tiene el mismo nombre que la imagen en MaskD
        output_files = [f for f in os.listdir(ruta_salida) if os.path.splitext(f)[0] == maskname]
        if not output_files:
            print(f"No se encontró en {ruta_salida} una imagen con el mismo nombre que {maskname}.")
            exit(1)

        output_file = os.path.join(ruta_salida, output_files[0])

        # Aplicar el comando magick composite con las opciones deseadas
        composite_command = f"magick composite -compose CopyOpacity {os.path.join(maskD, mask)} {output_file} {os.path.join(maskS, 'result.png')}"
        os.system(composite_command)

        # Obtener el nombre del archivo en output sin ninguna extensión
        name = os.path.splitext(os.path.basename(output_file))[0]

        # Renombrar el archivo result.png con el nombre del archivo en output y la extensión .png
        os.rename(os.path.join(maskS, "result.png"), os.path.join(maskS, f"{name}.png"))

        # Guardar el directorio actual en una variable
        original_dir = os.getcwd()

        # Cambiar al directorio de la carpeta MaskS
        os.chdir(maskS)

        # Iterar a través de los archivos de imagen en la carpeta MaskS
        for imagen in sorted(os.listdir(".")):
            # Obtener el nombre de la imagen sin la extensión
            nombre, extension = os.path.splitext(imagen)
            # Obtener solo el número de la imagen
            numero = "".join(filter(str.isdigit, nombre))
            # Definir el nombre de la siguiente imagen
            siguiente = f"{int(numero)+1:0{len(numero)}}{extension}"
            # Renombrar la imagen
            os.rename(imagen, siguiente)

        # Volver al directorio original
        os.chdir(original_dir)

        # Establecer un valor predeterminado para disolución
        if frame_refresh_frequency < 1:
            dissolve = percentage
        else:
            dissolve = 100 if loop_count % frame_refresh_frequency != 0 else refresh_strength

        # Obtener el nombre del archivo en MaskS sin la extensión
        maskS_files = [f for f in os.listdir(maskS) if os.path.isfile(os.path.join(maskS, f)) and f.endswith(".png")]
        if maskS_files:
            filename = os.path.splitext(maskS_files[0])[0]
        else:
            print(f"No se encontraron archivos de imagen en la carpeta '{maskS}'")
            filename = ""[0]

        # Salir del bucle si no hay más imágenes que procesar
        if not filename:
            break

        # Obtener la extensión del archivo en Gen con el mismo nombre
        gen_files = [f for f in os.listdir(ruta_entrada_2) if os.path.isfile(os.path.join(ruta_entrada_2, f)) and f.startswith(filename)]
        if gen_files:
            ext = os.path.splitext(gen_files[0])[1]
        else:
            print(f"No se encontró ningún archivo con el nombre '{filename}' en la carpeta '{ruta_entrada_2}'")
            ext = ""

        # Componer la imagen de MaskS y Gen con disolución (si está definido) y guardarla en la carpeta de salida
        os.system(
            f"magick composite {'-dissolve ' + str(dissolve) + '%' if dissolve is not None else ''} {maskS}/{filename}.png {ruta_entrada_2}/{filename}{ext} {ruta_salida}/{filename}{ext}"
        )

        denoise_loop = inter_denoise_speed
        kernel1 = inter_denoise
        kernel2 = inter_denoise_size

        # Demo plus bilateral
        if loop_count % denoise_loop == 0:
            # listar archivos en la carpeta de salida
            archivos = os.listdir(ruta_salida)
            # obtener el último archivo
            ultimo_archivo = os.path.join(ruta_salida, archivos[-1])
            # cargar imagen con opencv
            imagen = cv2.imread(ultimo_archivo)
            # aplicar filtro bilateral
            imagen_filtrada = cv2.bilateralFilter(imagen, 9, 9, 9)
            # sobreescribir el original
            cv2.imwrite(ultimo_archivo, imagen_filtrada)

        # Obtener el nombre del archivo más bajo en la carpeta MaskD
        maskd_files = [f for f in os.listdir(maskD) if os.path.isfile(os.path.join(maskD, f)) and f.startswith("")]
        if maskd_files:
            maskd_file = os.path.join(maskD, sorted(maskd_files)[0])
            os.remove(maskd_file)

        # Obtener el nombre del archivo más bajo en la carpeta MaskS
        masks_files = [f for f in os.listdir(maskS) if os.path.isfile(os.path.join(maskS, f)) and f.startswith("")]
        if masks_files:
            masks_file = os.path.join(maskS, sorted(masks_files)[0])
            os.remove(masks_file)

        # Aumentar el contador de bucles
        loop_count += 1


def dyndef(ruta_entrada_3, ruta_salida_1, ddf_strength):
    if ddf_strength <= 0:  # Condición 1: strength debe ser mayor a 0
        return
    imgs = []
    files = os.listdir(ruta_entrada_3)

    for file in files:
        img = cv2.imread(os.path.join(ruta_entrada_3, file))
        imgs.append(img)

    for idx in range(len(imgs) - 1, 0, -1):
        current_img = imgs[idx]
        prev_img = imgs[idx - 1]
        alpha = ddf_strength

        current_img = cv2.addWeighted(current_img, alpha, prev_img, 1 - alpha, 0)
        imgs[idx] = current_img

        if not os.path.exists(ruta_salida_1):
            os.makedirs(ruta_salida_1)

        output_path = os.path.join(ruta_salida_1, files[idx])  # Usa el mismo nombre que el original
        cv2.imwrite(output_path, current_img)

    # Copia el primer archivo de los originales al finalizar el proceso
    shutil.copy(os.path.join(ruta_entrada_3, files[0]), os.path.join(ruta_salida_1, files[0]))


def overlay_images(image1_path, image2_path, over_strength):
    opacity = over_strength

    # Abrir las imágenes
    image1 = Image.open(image1_path).convert("RGBA")
    image2 = Image.open(image2_path).convert("RGBA")

    # Alinear el tamaño de las imágenes
    if image1.size != image2.size:
        image2 = image2.resize(image1.size)

    # Convertir las imágenes en matrices NumPy
    np_image1 = np.array(image1).astype(np.float64) / 255.0
    np_image2 = np.array(image2).astype(np.float64) / 255.0

    # Aplicar el método de fusión "overlay" a las imágenes
    def basic(target, blend, opacity):
        return target * opacity + blend * (1 - opacity)

    def blender(func):
        def blend(target, blend, opacity=1, *args):
            res = func(target, blend, *args)
            res = basic(res, blend, opacity)
            return np.clip(res, 0, 1)

        return blend

    class Blend:
        @classmethod
        def method(cls, name):
            return getattr(cls, name)

        normal = basic

        @staticmethod
        @blender
        def overlay(target, blend, *args):
            return (target > 0.5) * (1 - (2 - 2 * target) * (1 - blend)) + (target <= 0.5) * (2 * target * blend)

    blended_image = Blend.overlay(np_image1, np_image2, opacity)

    # Convertir la matriz de vuelta a una imagen PIL
    blended_image = Image.fromarray((blended_image * 255).astype(np.uint8), "RGBA").convert("RGB")

    # Guardar la imagen resultante
    return blended_image


def overlay_images2(image1_path, image2_path, fuse_strength):
    opacity = fuse_strength

    try:
        image1 = Image.open(image1_path).convert("RGBA")
        image2 = Image.open(image2_path).convert("RGBA")
    except:
        print("No more frames to fuse.")
        return

    # Alinear el tamaño de las imágenes
    if image1.size != image2.size:
        image1 = image1.resize(image2.size)

    # Convertir las imágenes en matrices NumPy
    np_image1 = np.array(image1).astype(np.float64) / 255.0
    np_image2 = np.array(image2).astype(np.float64) / 255.0

    # Aplicar el método de fusión "overlay" a las imágenes
    def basic(target, blend, opacity):
        return target * opacity + blend * (1 - opacity)

    def blender(func):
        def blend(target, blend, opacity=1, *args):
            res = func(target, blend, *args)
            res = basic(res, blend, opacity)
            return np.clip(res, 0, 1)

        return blend

    class Blend:
        @classmethod
        def method(cls, name):
            return getattr(cls, name)

        normal = basic

        @staticmethod
        @blender
        def overlay(target, blend, *args):
            return (target > 0.5) * (1 - (2 - 2 * target) * (1 - blend)) + (target <= 0.5) * (2 * target * blend)

    blended_image = Blend.overlay(np_image1, np_image2, opacity)

    # Convertir la matriz de vuelta a una imagen PIL
    blended_image = Image.fromarray((blended_image * 255).astype(np.uint8), "RGBA").convert("RGB")

    # Guardar la imagen resultante
    return blended_image


def overlay_run(ruta_entrada_3, ruta_salida_1, ddf_strength, over_strength):
    if over_strength <= 0:  # Condición 1: strength debe ser mayor a 0
        return

    # Si ddf_strength y/o over_strength son mayores a 0, utilizar ruta_salida_1 en lugar de ruta_entrada_3
    if ddf_strength > 0:
        ruta_entrada_3 = ruta_salida_1

    if not os.path.exists("overtemp"):
        os.makedirs("overtemp")

    if not os.path.exists(ruta_salida_1):
        os.makedirs(ruta_salida_1)

    gen_path = ruta_entrada_3
    images = os.listdir(gen_path)
    image1_path = os.path.join(gen_path, images[0])
    image2_path = os.path.join(gen_path, images[1])

    fused_image = overlay_images(image1_path, image2_path, over_strength)
    fuseover_path = "overtemp"
    filename = os.path.basename(image1_path)
    fused_image.save(os.path.join(fuseover_path, filename))

    # Obtener una lista de todos los archivos en la carpeta "Gen"
    gen_files = os.listdir(ruta_entrada_3)

    for i in range(len(gen_files) - 1):
        image1_path = os.path.join(ruta_entrada_3, gen_files[i])
        image2_path = os.path.join(ruta_entrada_3, gen_files[i + 1])
        blended_image = overlay_images(image1_path, image2_path, over_strength)
        blended_image.save(os.path.join("overtemp", gen_files[i + 1]))

    # Definimos la ruta de la carpeta "overtemp"
    ruta_overtemp = "overtemp"

    # Movemos todos los archivos de la carpeta "overtemp" a la carpeta "ruta_salida"
    for archivo in os.listdir(ruta_overtemp):
        origen = os.path.join(ruta_overtemp, archivo)
        destino = os.path.join(ruta_salida_1, archivo)
        shutil.move(origen, destino)

    # Ajustar contraste y brillo para cada imagen en la carpeta de entrada
    if over_strength >= 0.4:
        for nombre_archivo in os.listdir(ruta_salida_1):
            # Cargar imagen
            ruta_archivo = os.path.join(ruta_salida_1, nombre_archivo)
            img = cv2.imread(ruta_archivo)

            # Ajustar contraste y brillo
            alpha = 1  # Factor de contraste (mayor que 1 para aumentar el contraste)
            beta = 10  # Valor de brillo (entero positivo para aumentar el brillo)
            img_contrast = cv2.convertScaleAbs(img, alpha=alpha, beta=beta)

            # Guardar imagen resultante en la carpeta de salida
            ruta_salida = os.path.join(ruta_salida_1, nombre_archivo)
            cv2.imwrite(ruta_salida, img_contrast)


def over_fuse(
    ruta_entrada_1,
    ruta_entrada_2,
    ruta_salida,
    denoise_blur,
    dfi_strength,
    dfi_deghost,
    inter_denoise,
    inter_denoise_size,
    inter_denoise_speed,
    fine_blur,
    frame_refresh_frequency,
    refresh_strength,
    smooth,
    frames_limit,
    ruta_entrada_3,
    ruta_salida_1,
    ddf_strength,
    over_strength,
    norm_strength,
    ruta_entrada_4,
    ruta_entrada_5,
    ruta_salida_2,
    fuse_strength,
    ruta_entrada_6,
    ruta_salida_3,
    fps_count,
):
    # Obtener una lista de todos los archivos en la carpeta "Gen"
    gen_files = os.listdir(ruta_entrada_4)

    # Ordenar la lista de archivos alfabéticamente
    gen_files.sort()

    # Obtener una lista de todos los archivos en la carpeta "Source"
    source_files = os.listdir(ruta_entrada_5)

    # Ordenar la lista de archivos alfabéticamente
    source_files.sort()

    if not os.path.exists(ruta_salida_2):
        os.makedirs(ruta_salida_2)

    for i in range(len(gen_files)):
        image1_path = os.path.join(ruta_entrada_4, gen_files[i])
        image2_path = os.path.join(ruta_entrada_5, source_files[i])
        blended_image = overlay_images2(image1_path, image2_path, fuse_strength)
        try:
            blended_image.save(os.path.join(ruta_salida_2, gen_files[i]))
        except Exception as e:
            print("Error al guardar la imagen:", str(e))
            print("No more frames to fuse")
            break


def norm(ruta_entrada_3, ruta_salida_1, ddf_strength, over_strength, norm_strength):
    if norm_strength <= 0:  # Condición 1: Norm_strength debe ser mayor a 0
        return

    # Si ddf_strength y/o over_strength son mayores a 0, utilizar ruta_salida_1 en lugar de ruta_entrada_3
    if ddf_strength > 0 or over_strength > 0:
        ruta_entrada_3 = ruta_salida_1

    # Crear la carpeta GenOverNorm si no existe
    if not os.path.exists("normtemp"):
        os.makedirs("normtemp")

    if not os.path.exists(ruta_salida_1):
        os.makedirs(ruta_salida_1)

    # Obtener una lista de todas las imágenes en la carpeta FuseOver
    img_list = os.listdir(ruta_entrada_3)
    img_list.sort()  # Ordenar la lista en orden ascendente

    # Iterar a través de las imágenes
    for i in range(len(img_list) - 1):
        # Cargar las dos imágenes a fusionar
        img1 = cv2.imread(os.path.join(ruta_entrada_3, img_list[i]))
        img2 = cv2.imread(os.path.join(ruta_entrada_3, img_list[i + 1]))

        # Calcular la luminosidad promedio de cada imagen
        avg1 = np.mean(cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY))
        avg2 = np.mean(cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY))

        # Calcular los pesos para cada imagen
        weight1 = avg1 / (avg1 + avg2)
        weight2 = avg2 / (avg1 + avg2)

        # Fusionar las imágenes utilizando los pesos
        result = cv2.addWeighted(img1, weight1, img2, weight2, 0)

        # Guardar la imagen resultante en la carpeta GenOverNorm con el mismo nombre que la imagen original
        cv2.imwrite(os.path.join("normtemp", img_list[i + 1]), result)

    # Copiar la primera imagen en la carpeta GenOverNorm para mantener la secuencia completa
    img0 = cv2.imread(os.path.join(ruta_entrada_3, img_list[0]))
    cv2.imwrite(os.path.join("normtemp", img_list[0]), img0)

    # Definimos la ruta de la carpeta "overtemp"
    ruta_overtemp = "normtemp"

    # Movemos todos los archivos de la carpeta "overtemp" a la carpeta "ruta_salida"
    for archivo in os.listdir(ruta_overtemp):
        origen = os.path.join(ruta_overtemp, archivo)
        destino = os.path.join(ruta_salida_1, archivo)
        shutil.move(origen, destino)


def deflickers(
    ruta_entrada_1,
    ruta_entrada_2,
    ruta_salida,
    denoise_blur,
    dfi_strength,
    dfi_deghost,
    inter_denoise,
    inter_denoise_size,
    inter_denoise_speed,
    fine_blur,
    frame_refresh_frequency,
    refresh_strength,
    smooth,
    frames_limit,
    ruta_entrada_3,
    ruta_salida_1,
    ddf_strength,
    over_strength,
    norm_strength,
    ruta_entrada_4,
    ruta_entrada_5,
    ruta_salida_2,
    fuse_strength,
    ruta_entrada_6,
    ruta_salida_3,
    fps_count,
):
    dyndef(ruta_entrada_3, ruta_salida_1, ddf_strength)
    overlay_run(ruta_entrada_3, ruta_salida_1, ddf_strength, over_strength)
    norm(ruta_entrada_3, ruta_salida_1, ddf_strength, over_strength, norm_strength)


def extract_video(
    ruta_entrada_1,
    ruta_entrada_2,
    ruta_salida,
    denoise_blur,
    dfi_strength,
    dfi_deghost,
    inter_denoise,
    inter_denoise_size,
    inter_denoise_speed,
    fine_blur,
    frame_refresh_frequency,
    refresh_strength,
    smooth,
    frames_limit,
    ruta_entrada_3,
    ruta_salida_1,
    ddf_strength,
    over_strength,
    norm_strength,
    ruta_entrada_4,
    ruta_entrada_5,
    ruta_salida_2,
    fuse_strength,
    ruta_entrada_6,
    ruta_salida_3,
    fps_count,
):
    # Ruta del archivo de video
    filename = ruta_entrada_6

    # Directorio donde se guardarán los frames extraídos
    output_dir = ruta_salida_3

    # Abrir el archivo de video
    cap = cv2.VideoCapture(filename)

    # Obtener los FPS originales del video
    fps = cap.get(cv2.CAP_PROP_FPS)

    # Si fps_count es 0, utilizar los FPS originales
    if fps_count == 0:
        fps_count = fps

    # Calcular el tiempo entre cada frame a extraer en milisegundos
    frame_time = int(round(1000 / fps_count))

    # Crear el directorio de salida si no existe
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Inicializar el contador de frames
    frame_count = 0

    # Inicializar el tiempo del último frame extraído
    last_frame_time = 0

    # Iterar sobre los frames del video
    while True:
        # Leer el siguiente frame
        ret, frame = cap.read()

        # Si no se pudo leer un frame, salir del loop
        if not ret:
            break

        # Calcular el tiempo actual del frame en milisegundos
        current_frame_time = int(round(cap.get(cv2.CAP_PROP_POS_MSEC)))

        # Si todavía no ha pasado suficiente tiempo desde el último frame extraído, saltar al siguiente frame
        if current_frame_time - last_frame_time < frame_time:
            continue

        # Incrementar el contador de frames
        frame_count += 1

        # Construir el nombre del archivo de salida
        output_filename = os.path.join(output_dir, "frame_{:04d}.jpeg".format(frame_count))

        # Guardar el frame como una imagen
        cv2.imwrite(output_filename, frame)

        # Actualizar el tiempo del último frame extraído
        last_frame_time = current_frame_time

    # Cerrar el archivo de video
    cap.release()

    # Mostrar información sobre el proceso finalizado
    print("Extracted {} frames.".format(frame_count))


def test_dfi(
    ruta_entrada_1,
    ruta_entrada_2,
    ruta_salida,
    denoise_blur,
    dfi_strength,
    dfi_deghost,
    inter_denoise,
    inter_denoise_size,
    inter_denoise_speed,
    fine_blur,
    frame_refresh_frequency,
    refresh_strength,
    smooth,
    frames_limit,
    ruta_entrada_3,
    ruta_salida_1,
    ddf_strength,
    over_strength,
    norm_strength,
    ruta_entrada_4,
    ruta_entrada_5,
    ruta_salida_2,
    fuse_strength,
    ruta_entrada_6,
    ruta_salida_3,
    fps_count,
):
    maskD = os.path.join(os.getcwd(), "extensions", "Abysz-LAB-Ext", "scripts", "Run", "MaskDT")
    # maskS = os.path.join(os.getcwd(), 'extensions', 'Abysz-LAB-Ext', 'scripts', 'Run', 'MaskST')
    # output = os.path.join(os.getcwd(), 'extensions', 'Abysz-lab', 'scripts', 'Run', 'Output')
    source = os.path.join(os.getcwd(), "extensions", "Abysz-LAB-Ext", "scripts", "Run", "SourceT")
    gen = os.path.join(os.getcwd(), "extensions", "Abysz-LAB-Ext", "scripts", "Run", "GenT")

    # verificar si las carpetas existen y eliminarlas si es el caso
    if os.path.exists(source):  # verificar si existe la carpeta source
        shutil.rmtree(source)  # eliminar la carpeta source y su contenido
    # if os.path.exists(maskS): # verificar si existe la carpeta maskS
    #    shutil.rmtree(maskS) # eliminar la carpeta maskS y su contenido
    if os.path.exists(maskD):  # verificar si existe la carpeta maskS
        shutil.rmtree(maskD)  # eliminar la carpeta maskS y su contenido
    if os.path.exists(gen):  # verificar si existe la carpeta maskS
        shutil.rmtree(gen)  # eliminar la carpeta maskS y su contenido
    # if os.path.exists(output): # verificar si existe la carpeta maskS
    #    shutil.rmtree(output) # eliminar la carpeta maskS y su contenido

    os.makedirs(source, exist_ok=True)
    # os.makedirs(maskS, exist_ok=True)
    # os.makedirs(output, exist_ok=True)
    os.makedirs(maskD, exist_ok=True)
    os.makedirs(gen, exist_ok=True)

    def copy_images(ruta_entrada_1, ruta_entrada_2):
        # Copiar todas las imágenes de la carpeta ruta_entrada_1 a la carpeta Source
        indices = [10, 11, 20, 21, 30, 31]  # Los índices de las imágenes que quieres copiar
        for i in indices:
            file = os.listdir(ruta_entrada_1)[i]  # Obtener el nombre del archivo en el índice i
            if file.endswith(".jpg") or file.endswith(".jpeg") or file.endswith(".png"):  # Verificar que sea una imagen
                img = Image.open(os.path.join(ruta_entrada_1, file))  # Abrir la imagen
                rgb_img = img.convert("RGB")  # Convertir a RGB
                rgb_img.save(
                    os.path.join("./extensions/Abysz-LAB-Ext/scripts/Run/SourceT", file), "jpeg", quality=100
                )  # Guardar la imagen en la carpeta destino
        for i in indices:
            file = os.listdir(ruta_entrada_2)[i]  # Obtener el nombre del archivo en el índice i
            if file.endswith(".jpg") or file.endswith(".jpeg") or file.endswith(".png"):  # Verificar que sea una imagen
                img = Image.open(os.path.join(ruta_entrada_2, file))  # Abrir la imagen
                rgb_img = img.convert("RGB")  # Convertir a RGB
                rgb_img.save(
                    os.path.join("./extensions/Abysz-LAB-Ext/scripts/Run/GenT", file), "jpeg", quality=100
                )  # Guardar la imagen en la carpeta destino

    # Llamar a la función copy_images para copiar las imágenes
    copy_images(ruta_entrada_1, ruta_entrada_2)

    # Carpeta donde se encuentran las imágenes de Gen
    def sresize(ruta_entrada_2):
        gen_folder = ruta_entrada_2

        # Carpeta donde se encuentran las imágenes de FULL
        full_folder = "./extensions/Abysz-LAB-Ext/scripts/Run/SourceT"

        # Obtener la primera imagen en la carpeta Gen
        gen_images = os.listdir(gen_folder)
        gen_image_path = os.path.join(gen_folder, gen_images[0])
        gen_image = cv2.imread(gen_image_path)
        gen_height, gen_width = gen_image.shape[:2]
        gen_aspect_ratio = gen_width / gen_height

        # Recorrer todas las imágenes en la carpeta FULL
        for image_name in os.listdir(full_folder):
            image_path = os.path.join(full_folder, image_name)
            image = cv2.imread(image_path)
            height, width = image.shape[:2]
            aspect_ratio = width / height

            if aspect_ratio != gen_aspect_ratio:
                if aspect_ratio > gen_aspect_ratio:
                    # La imagen es más ancha que la imagen de Gen
                    crop_width = int(height * gen_aspect_ratio)
                    x = int((width - crop_width) / 2)
                    image = image[:, x : x + crop_width]
                else:
                    # La imagen es más alta que la imagen de Gen
                    crop_height = int(width / gen_aspect_ratio)
                    y = int((height - crop_height) / 2)
                    image = image[y : y + crop_height, :]

            # Redimensionar la imagen de FULL a la resolución de la imagen de Gen
            image = cv2.resize(image, (gen_width, gen_height))

            # Guardar la imagen redimensionada en la carpeta FULL
            cv2.imwrite(os.path.join(full_folder, image_name), image)

    sresize(ruta_entrada_2)

    def s_g_rename(ruta_entrada_2):
        source_dir = "./extensions/Abysz-LAB-Ext/scripts/Run/SourceT"  # ruta de la carpeta "Source"

        # Obtener una lista de los nombres de archivo en la carpeta "Source"
        files = os.listdir(source_dir)

        # Renombrar cada archivo
        for i, file_name in enumerate(files):
            old_path = os.path.join(source_dir, file_name)  # ruta actual del archivo
            new_file_name = f"{i+1:04d}"  # nuevo nombre de archivo con formato %04d
            new_path = os.path.join(source_dir, new_file_name + os.path.splitext(file_name)[1])  # nueva ruta del archivo
            try:
                os.rename(old_path, new_path)
            except FileExistsError:
                print(f"El archivo {new_file_name} ya existe. Se omite su renombre.")

        gen_dir = "./extensions/Abysz-LAB-Ext/scripts/Run/GenT"  # ruta de la carpeta "Source"

        # Obtener una lista de los nombres de archivo en la carpeta ruta_entrada_2
        files = os.listdir(gen_dir)

        # Renombrar cada archivo
        for i, file_name in enumerate(files):
            old_path = os.path.join(gen_dir, file_name)  # ruta actual del archivo
            new_file_name = f"{i+1:04d}"  # nuevo nombre de archivo con formato %04d
            new_path = os.path.join(gen_dir, new_file_name + os.path.splitext(file_name)[1])  # nueva ruta del archivo
            try:
                os.rename(old_path, new_path)
            except FileExistsError:
                print(f"El archivo {new_file_name} ya existe. Se omite su renombre.")

    s_g_rename(ruta_entrada_2)

    # Obtener el primer archivo de la carpeta ruta_entrada_2
    # gen_files = os.listdir(ruta_entrada_2)
    # if gen_files:
    #    first_gen_file = gen_files[0]
    #
    #    # Copiar el archivo a la carpeta "Output" y reemplazar si ya existe
    #    output_file = os.path.join(output, first_gen_file)
    #    shutil.copyfile(os.path.join(ruta_entrada_2, first_gen_file), output_file)
    # subprocess call
    def denoise(denoise_blur):
        if denoise_blur < 1:
            return

        denoise_kernel = denoise_blur
        # Obtener la lista de nombres de archivos en la carpeta source
        files = os.listdir("./extensions/Abysz-LAB-Ext/scripts/Run/SourceT")

        # Crear una carpeta destino si no existe
        # if not os.path.exists("dest"):
        #   os.mkdir("dest")

        # Recorrer cada archivo en la carpeta source
        for file in files:
            # Leer la imagen con opencv
            img = cv2.imread(os.path.join("./extensions/Abysz-LAB-Ext/scripts/Run/SourceT", file))

            # Aplicar el filtro de blur con un tamaño de kernel 5x5
            dst = cv2.bilateralFilter(img, denoise_kernel, 31, 31)

            # Eliminar el archivo original
            # os.remove(os.path.join("SourceDFI", file))

            # Guardar la imagen resultante en la carpeta destino con el mismo nombre
            cv2.imwrite(os.path.join("./extensions/Abysz-LAB-Ext/scripts/Run/SourceT", file), dst)

    denoise(denoise_blur)

    # Definir la carpeta donde están los archivos
    carpeta = "./extensions/Abysz-LAB-Ext/scripts/Run/SourceT"

    # Crear la carpeta MaskD si no existe
    os.makedirs("./extensions/Abysz-LAB-Ext/scripts/Run/MaskDT", exist_ok=True)

    # Inicializar número de imagen
    numero = 1

    umbral_size = dfi_strength
    # Iterar a través de los archivos de imagen en la carpeta Source
    for filename in sorted(os.listdir(carpeta)):
        # Cargar la imagen actual en escala de grises
        actual = cv2.imread(os.path.join(carpeta, filename), cv2.IMREAD_GRAYSCALE)

        # Si el número de imagen es par, procesar la imagen actual y la anterior
        if numero % 2 == 0:
            diff = cv2.absdiff(anterior, actual)

            # Aplicar un umbral y guardar la imagen resultante en la carpeta MaskD con el mismo nombre que el original. Menos es más.
            umbral = umbral_size
            umbralizado = cv2.threshold(diff, umbral, 255, cv2.THRESH_BINARY_INV)[1]  # Invertir los colores
            cv2.imwrite(os.path.join("./extensions/Abysz-LAB-Ext/scripts/Run/MaskDT", filename), umbralizado)

        # Guardar la imagen actual como anterior para el siguiente ciclo
        anterior = actual

        # Incrementar el número de imagen para alternar entre pares e impares
        numero += 1

    # Obtener la lista de los nombres de los archivos en la carpeta MaskD
    files = os.listdir("./extensions/Abysz-LAB-Ext/scripts/Run/MaskDT")
    # Definir la carpeta donde están los archivos
    carpeta = "./extensions/Abysz-LAB-Ext/scripts/Run/MaskDT"
    blur_kernel = smooth

    # Iterar sobre cada archivo
    for file in files:
        if dfi_deghost == 0:
            continue
        # Leer la imagen de la carpeta MaskD
        # img = cv2.imread("MaskD" + file)
        img = cv2.imread(os.path.join("./extensions/Abysz-LAB-Ext/scripts/Run/MaskDT", file))

        # Invertir la imagen usando la función bitwise_not()
        img_inv = cv2.bitwise_not(img)

        kernel_size = dfi_deghost

        # Dilatar la imagen usando la función dilate()
        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (kernel_size, kernel_size)
        )  # Puedes cambiar el tamaño y la forma del kernel según tus preferencias
        img_dil = cv2.dilate(img_inv, kernel)

        # Volver a invertir la imagen usando la función bitwise_not()
        img_out = cv2.bitwise_not(img_dil)

        # Sobrescribir la imagen en la carpeta MaskD con el mismo nombre que el original
        # cv2.imwrite("MaskD" + file, img_out)
        # cv2.imwrite(os.path.join("MaskD", file, img_out))
        filename = os.path.join("./extensions/Abysz-LAB-Ext/scripts/Run/MaskDT", file)
        cv2.imwrite(filename, img_out)

    # Iterar a través de los archivos de imagen en la carpeta MaskD
    if smooth > 1:
        for imagen in os.listdir(carpeta):
            if imagen.endswith(".jpg") or imagen.endswith(".png") or imagen.endswith(".jpeg"):
                # Leer la imagen
                img = cv2.imread(os.path.join(carpeta, imagen))
                # Aplicar el filtro
                img = cv2.GaussianBlur(img, (blur_kernel, blur_kernel), 0)
                # Guardar la imagen con el mismo nombre
                cv2.imwrite(os.path.join(carpeta, imagen), img)

    nombres = os.listdir("./extensions/Abysz-LAB-Ext/scripts/Run/MaskDT")  # obtener los nombres de los archivos en la carpeta MaskDT
    ancho = 0  # variable para guardar el ancho acumulado de las ventanas
    for i, nombre in enumerate(nombres):  # recorrer cada nombre de archivo
        imagen = cv2.imread("./extensions/Abysz-LAB-Ext/scripts/Run/MaskDT/" + nombre)  # leer la imagen correspondiente
        h, w, c = imagen.shape  # obtener el alto, ancho y canales de la imagen
        aspect_ratio = w / h  # calcular la relación de aspecto
        cv2.namedWindow(nombre, cv2.WINDOW_NORMAL)  # crear una ventana con el nombre del archivo
        ancho_ventana = 500  # definir un ancho fijo para las ventanas
        alto_ventana = int(ancho_ventana / aspect_ratio)  # calcular el alto proporcional al ancho y a la relación de aspecto
        cv2.resizeWindow(nombre, ancho_ventana, alto_ventana)  # cambiar el tamaño de la ventana según las dimensiones calculadas
        cv2.moveWindow(nombre, ancho, 0)  # mover la ventana a una posición horizontal según el ancho acumulado
        cv2.imshow(nombre, imagen)  # mostrar la imagen en la ventana
        cv2.setWindowProperty(nombre, cv2.WND_PROP_TOPMOST, 1.0)  # poner la ventana en primer plano con un valor double
        ancho += ancho_ventana + 10  # aumentar el ancho acumulado en 410 píxeles para la siguiente ventana
    cv2.waitKey(4000)  # esperar a que se presione una tecla para cerrar todas las ventanas
    cv2.destroyAllWindows()  # cerrar todas las ventanas abiertas por OpenCV


def add_tab():
    print("LAB")
    with gr.Blocks(analytics_enabled=False) as demo:
        with gr.Tabs():
            with gr.Tab("Main"):
                with gr.Row():
                    with gr.Column():
                        with gr.Column():
                            gr.Markdown("# Abysz LAB 0.1.7 Temporal coherence tools")
                            gr.Markdown("## DFI Render")
                        with gr.Column():
                            ruta_entrada_1 = gr.Textbox(
                                label="Original frames folder", placeholder="The RAW frames you have used as base for IA generation."
                            )
                            ruta_entrada_2 = gr.Textbox(label="Generated frames folder", placeholder="The frames of AI generated video")
                            ruta_salida = gr.Textbox(
                                label="Output folder", placeholder="Remember that each generation overwrites previous frames in the same folder."
                            )
                        with gr.Accordion("Info", open=False):
                            gr.Markdown(
                                "### **The new algorithm will adapt to DFI tolerance to choose the parameters for each frame. IMPORTANT: The algorithm is optimized to maintain a balance between deflicking and corruption, so that it is easier to use StableDiffusion at low denoising to reconstruct lost detail while preserving the stability gained.**"
                            )
                            gr.Markdown(
                                "**Source denoise:** A noisy source can interfere with the accuracy of the scan. This will reduce noise, but also detail. However, this does not affect the original, and sometimes flatter images are not bad for the process, although you may need to balance by reducing the DFI tolerance. **(This is a demanding algorithm)**"
                            )
                            gr.Markdown(
                                "**DFI Tolerance:** Determines the movement tolerance of the scan. Low tolerance will detect even small changes in static areas. High values will detect less movements. Ideally, it should detect the movements that are important to you, and skip the static and useless areas, reducing the flick in those. **This parameter commands the new dynamic algorithm.** "
                            )
                            gr.Markdown(
                                "**DFI Expand:** DFI expand fattens the edges of the areas detected by DFI. Note: DFI tolerance modifies the amount of movement detected. This only affects that result, be it big or small. Its a complementary parameter. 0=Off."
                            )
                        with gr.Row():
                            denoise_blur = gr.Slider(minimum=0, maximum=50, value=0, step=1, label="Source Denoise")
                            dfi_strength = gr.Slider(minimum=0.5, maximum=15, value=5, step=0.5, label="DFI Tolerance")
                            dfi_deghost = gr.Slider(minimum=0, maximum=10, value=0, step=1, label="DFI Expand")
                        with gr.Accordion("Info", open=False):
                            gr.Markdown(
                                "Here you can check 3 examples of the motion map for those parameters. It is useful, for example, to adjust denoise if you see that it detects unnecessary graininess. Keep in mind that what you see represents movement between two frames."
                            )
                            gr.Markdown(
                                "The black is basically what it won't process (it will let it through to preserve the movement), and the white what it will try to keep stable in that frame interpolation. Try freely. Here you can also test how the manual blur works (advanced section)."
                            )
                        dfi_test = gr.Button(value="Preview DFI Map")
                        with gr.Accordion("Advanced", open=False):
                            with gr.Accordion("Info", open=False):
                                gr.Markdown(
                                    "**Inter Denoise:** Reduces render pixelation generated by corruption. However, be careful. It's resource hungry, and might remove excess detail. Not recommended to change size or FPD, but to use Stable Diffusion to remove the pixelation later."
                                )
                                gr.Markdown(
                                    "**Inter Blur:** Fine tunes the dynamic blur algorithm for DFI map. Lower = Stronger blur effects. Between 2-3 recommended."
                                )
                                gr.Markdown(
                                    "**Corruption Refresh:** To reduce the distortion generated by the process, you can recover original information every X number of frames. Lower number = faster refresh."
                                )
                                gr.Markdown(
                                    "**Corruption Preserve:** Here you decide how much corruption keep in each corruption refresh. Low values will recover more of the original frame, with its changes and flickering, in exchange for reducing corruption. You must find the balance that works best for your goal."
                                )
                                gr.Markdown(
                                    "**Smooth:** This smoothes the edges of the interpolated areas. Low values are currently recommended until the algorithm is updated."
                                )
                            with gr.Row():
                                inter_denoise = gr.Slider(minimum=1, maximum=25, value=9, step=1, label="Inter Denoise")
                                inter_denoise_size = gr.Slider(minimum=1, maximum=25, value=9, step=2, label="Inter Denoise Size")
                                inter_denoise_speed = gr.Slider(minimum=1, maximum=15, value=3, step=1, label="Inter Denoise FPD")
                                fine_blur = gr.Slider(minimum=1, maximum=5, value=3, step=0.1, label="Inter Blur")
                            gr.Markdown("### The new dynamic algorithm will handle these parameters. Activate them only for manual control.")
                            with gr.Row():
                                frame_refresh_frequency = gr.Slider(
                                    minimum=0, maximum=30, value=0, step=1, label="Corruption Refresh (Lower = Faster)"
                                )
                                refresh_strength = gr.Slider(minimum=0, maximum=100, value=0, step=5, label="Corruption Preserve")
                                smooth = gr.Slider(minimum=1, maximum=99, value=1, step=2, label="Smooth")
                        with gr.Row():
                            frames_limit = gr.Number(label="Frames to render. 0=ALL")
                            run_button = gr.Button(value="Run DFI", variant="primary")
                            output_placeholder = gr.Textbox(label="Status", placeholder="STAND BY...")
                    with gr.Column():
                        with gr.Column():
                            gr.Markdown("# |")
                            gr.Markdown("## Deflickers Playground")
                            with gr.Column():
                                ruta_entrada_3 = gr.Textbox(label="Frames folder", placeholder="Frames to process")
                                ruta_salida_1 = gr.Textbox(label="Output folder", placeholder="Processed frames")
                                with gr.Accordion("Info", open=False):
                                    gr.Markdown(
                                        "I made this series of deflickers based on the standard that Vegas Pro includes. You can use them together or separately. Be careful when mixing them."
                                    )
                                    gr.Markdown(
                                        "**Blend:** Blends a percentage of the previous frame with the next. This can soften transitions and highlights. High values will add too much information."
                                    )
                                    gr.Markdown(
                                        "**Overlay:** Use the overlay image blending mode. Note that it works particularly good at mid-high values, wich will modify the overall contrast. You will have to decide what works for you."
                                    )
                                    gr.Markdown(
                                        "**Normalize:** Calculates the average between frames to merge them. It may be more practical if you don't have a specific Blend deflicker value in mind."
                                    )
                                ddf_strength = gr.Slider(minimum=0, maximum=1, value=0, step=0.01, label="BLEND (0=Off)")
                                over_strength = gr.Slider(minimum=0, maximum=1, value=0, step=0.01, label="OVERLAY (0=Off)")
                                norm_strength = gr.Slider(minimum=0, maximum=1, value=0, step=1, label="NORMALIZE (0=Off))")
                                dfk_button = gr.Button(value="Deflickers")
            with gr.Tab("LAB Tools"):
                with gr.Column():
                    gr.Markdown("## Style Fuse")
                    with gr.Accordion("Info", open=False):
                        gr.Markdown(
                            "With this you can merge two sets of frames with overlay technique. For example, you can take a style video that is just lights and/or colors, and overlay it on top of another video."
                        )
                        gr.Markdown(
                            "The resulting video will be useful for use in Img2Img Batch and that the AI render preserves these added color and lighting details, along with the details of the original video."
                        )
                    with gr.Row():
                        ruta_entrada_4 = gr.Textbox(label="Style frames", placeholder="Style to fuse")
                        ruta_entrada_5 = gr.Textbox(label="Video frames", placeholder="Frames to process")
                    with gr.Row():
                        ruta_salida_2 = gr.Textbox(label="Output folder", placeholder="Processed frames")
                        fuse_strength = gr.Slider(minimum=0.1, maximum=1, value=0.5, step=0.01, label="Fuse Strength")
                        fuse_button = gr.Button(value="Fuse")
                    gr.Markdown("## Video extract")
                    with gr.Row():
                        ruta_entrada_6 = gr.Textbox(label="Video path", placeholder="Remember to use same fps as generated video for DFI")
                        ruta_salida_3 = gr.Textbox(label="Output folder", placeholder="Processed frames")
                    with gr.Row():
                        fps_count = gr.Number(label="Fps. 0=Original")
                        vidextract_button = gr.Button(value="Extract")
                    output_placeholder2 = gr.Textbox(label="Status", placeholder="STAND BY...")
            with gr.Tab("Guide"):
                with gr.Column():
                    gr.Markdown("# What DFI does?")
                    with gr.Accordion("Info", open=False):
                        gr.Markdown(
                            "DFI processing analyzes the motion of the original video, and attempts to force that information into the generated video. Demo on https://github.com/AbyszOne/Abysz-LAB-Ext"
                        )
                        gr.Markdown(
                            "In short, this will reduce flicker in areas of the video that don't need to change, but SD does. For example, for a man smoking, leaning against a pole, it will detect that the pole is static, and will try to prevent it from changing as much as possible."
                        )
                        gr.Markdown("This is an aggressive process that requires a lot of control for each context. Read the recommended strategies.")
                        gr.Markdown(
                            "Although Video to Video is the most efficient way, a DFI One Shot method is under experimental development as well."
                        )
                    gr.Markdown("# Usage strategies")
                    with gr.Accordion("Info", open=False):
                        gr.Markdown(
                            "If you get enough understanding of the tool, you can achieve a much more stable and clean enough rendering. However, this is quite demanding."
                        )
                        gr.Markdown(
                            "Instead, a much friendlier and faster way to use this tool is as an intermediate step. For this, you can allow a reasonable degree of corruption in exchange for more general stability. "
                        )
                        gr.Markdown(
                            "You can then clean up the corruption and recover details with a second step in Stable Diffusion at low denoising (0.2-0.4), using the same parameters and seed."
                        )
                        gr.Markdown(
                            "In this way, the final result will have the stability that we have gained, maintaining final detail. If you find a balanced workflow, you will get something at least much more coherent and stable than the raw AI render."
                        )
        inputs = [
            ruta_entrada_1,
            ruta_entrada_2,
            ruta_salida,
            denoise_blur,
            dfi_strength,
            dfi_deghost,
            inter_denoise,
            inter_denoise_size,
            inter_denoise_speed,
            fine_blur,
            frame_refresh_frequency,
            refresh_strength,
            smooth,
            frames_limit,
            ruta_entrada_3,
            ruta_salida_1,
            ddf_strength,
            over_strength,
            norm_strength,
            ruta_entrada_4,
            ruta_entrada_5,
            ruta_salida_2,
            fuse_strength,
            ruta_entrada_6,
            ruta_salida_3,
            fps_count,
        ]
        dfi_test.click(fn=test_dfi, inputs=inputs, outputs=output_placeholder)
        run_button.click(fn=main, inputs=inputs, outputs=output_placeholder)
        dfk_button.click(fn=deflickers, inputs=inputs, outputs=output_placeholder)
        fuse_button.click(fn=over_fuse, inputs=inputs, outputs=output_placeholder2)
        vidextract_button.click(fn=extract_video, inputs=inputs, outputs=output_placeholder2)
    return [(demo, "Abysz LAB", "demo")]


script_callbacks.on_ui_tabs(add_tab)
