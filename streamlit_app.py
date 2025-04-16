import streamlit as st
import pandas as pd
import zipfile
import io
import os
import tempfile
import shutil
import base64
from PIL import Image

# Configuration de la page
st.set_page_config(
    page_title="Correspondance EAN-Images",
    page_icon="🔍",
    layout="wide"
)

# Titre et description
st.title("Application de correspondance EAN-Images")
st.markdown("""
Cette application permet de filtrer des images selon leur correspondance avec des codes EAN.
1. Téléchargez votre fichier Excel contenant les codes EAN
2. Téléchargez votre archive ZIP contenant les images
3. Sélectionnez la feuille Excel et la colonne contenant les EANs
4. Lancez le traitement
""")

# Fonction pour créer un lien de téléchargement
def get_binary_file_downloader_html(bin_file, file_label='Fichier'):
    with open(bin_file, 'rb') as f:
        data = f.read()
    bin_str = base64.b64encode(data).decode()
    href = f'<a href="data:application/zip;base64,{bin_str}" download="{os.path.basename(bin_file)}" class="download-link">Télécharger {file_label}</a>'
    return href

# Création de colonnes pour organiser l'interface
col1, col2 = st.columns(2)

with col1:
    # Zone de téléchargement du fichier Excel
    st.subheader("1. Téléchargez votre fichier Excel")
    excel_file = st.file_uploader("Choisissez un fichier Excel", type=["xlsx", "xls"])
    
    if excel_file is not None:
        # Lecture des noms de feuilles disponibles
        try:
            xl = pd.ExcelFile(excel_file)
            sheets = xl.sheet_names
            
            # Sélection de la feuille
            selected_sheet = st.selectbox("Sélectionnez une feuille", sheets)
            
            # Lecture du DataFrame
            df = pd.read_excel(excel_file, sheet_name=selected_sheet)
            
            # Affichage de l'aperçu
            st.subheader("Aperçu des données")
            st.dataframe(df.head())
            
            # Sélection de la colonne EAN
            ean_column = st.selectbox(
                "Sélectionnez la colonne contenant les EANs", 
                df.columns,
                index=list(df.columns).index("EAN") if "EAN" in df.columns else 0
            )
            
            # Affichage des premiers EANs
            st.write(f"Exemples d'EANs trouvés dans la colonne '{ean_column}':")
            ean_examples = df[ean_column].dropna().head(5).tolist()
            st.code("\n".join(str(ean) for ean in ean_examples))
            
        except Exception as e:
            st.error(f"Erreur lors de la lecture du fichier Excel: {str(e)}")
            st.stop()
    else:
        st.info("Veuillez télécharger un fichier Excel pour continuer.")
        st.stop()

with col2:
    # Zone de téléchargement du fichier ZIP
    st.subheader("2. Téléchargez votre archive ZIP d'images")
    zip_file = st.file_uploader("Choisissez un fichier ZIP contenant les images", type=["zip"])
    
    if zip_file is not None:
        # Informations sur le fichier ZIP
        with zipfile.ZipFile(zip_file) as z:
            file_list = z.namelist()
            image_files = [f for f in file_list if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            
            st.write(f"Nombre total de fichiers dans le ZIP: {len(file_list)}")
            st.write(f"Nombre d'images trouvées: {len(image_files)}")
            
            if len(image_files) > 0:
                st.write("Exemples de noms d'images:")
                st.code("\n".join(image_files[:5]))
                
                # Afficher quelques images d'exemple
                st.subheader("Aperçu des images")
                images_to_show = min(3, len(image_files))
                image_cols = st.columns(images_to_show)
                
                for i in range(images_to_show):
                    try:
                        with z.open(image_files[i]) as img_file:
                            img = Image.open(img_file)
                            with image_cols[i]:
                                st.image(img, caption=image_files[i], width=150)
                    except Exception as e:
                        with image_cols[i]:
                            st.error(f"Impossible d'afficher l'image: {str(e)}")
            else:
                st.warning("Aucune image trouvée dans le fichier ZIP.")
                st.stop()
    else:
        st.info("Veuillez télécharger un fichier ZIP pour continuer.")
        st.stop()

# Zone de paramètres du traitement
st.subheader("3. Options de correspondance")
with st.expander("Paramètres avancés", expanded=True):
    col1, col2 = st.columns(2)
    
    with col1:
        match_png = st.checkbox("Chercher les correspondances PNG (_1.png)", value=True)
        alternate_png = st.checkbox("Chercher les PNG sans suffixe (.png)", value=False)
    
    with col2:
        match_jpg = st.checkbox("Chercher les correspondances JPG (_1.jpg)", value=True)
        alternate_jpg = st.checkbox("Chercher les JPG sans suffixe (.jpg)", value=False)

# Bouton pour lancer le traitement
st.subheader("4. Lancer le traitement")
run_button = st.button("Lancer la correspondance EAN-Images", type="primary")

if run_button:
    if excel_file is None or zip_file is None:
        st.error("Veuillez télécharger tous les fichiers requis.")
        st.stop()
    
    # Créer un dossier temporaire pour stocker les résultats
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = os.path.join(temp_dir, "correspondance")
        os.makedirs(output_dir, exist_ok=True)
        
        # Extraire les EANs du DataFrame
        eans = df[ean_column].dropna().astype(str).tolist()
        eans = [str(ean).split('.')[0] if '.' in str(ean) else str(ean) for ean in eans]
        
        # Préparer les patterns à rechercher
        patterns = []
        if match_png:
            patterns.append("_1.png")
        if match_jpg:
            patterns.append("_1.jpg")
        if alternate_png:
            patterns.append(".png")
        if alternate_jpg:
            patterns.append(".jpg")
        
        if not patterns:
            st.error("Veuillez sélectionner au moins un type de correspondance d'image.")
            st.stop()
        
        st.write(f"Recherche de correspondance pour {len(eans)} EANs...")
        
        # Créer un conteneur de progression
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Compter les correspondances
        matches_found = 0
        
        # Extraire les images correspondantes
        with zipfile.ZipFile(zip_file) as z_in:
            file_list = z_in.namelist()
            
            # Filtrer pour n'obtenir que les fichiers image
            image_files = [f for f in file_list if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            
            # Créer un fichier ZIP pour les résultats
            output_zip_path = os.path.join(temp_dir, "resultats_correspondance.zip")
            
            with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as z_out:
                # Pour chaque EAN, chercher les fichiers correspondants
                for i, ean in enumerate(eans):
                    progress_bar.progress((i + 1) / len(eans))
                    status_text.text(f"Traitement de l'EAN {i+1}/{len(eans)}: {ean}")
                    
                    # Chercher les correspondances
                    for pattern in patterns:
                        filename = f"{ean}{pattern}"
                        for image_file in image_files:
                            if os.path.basename(image_file) == filename:
                                # Ajouter au ZIP de sortie
                                with z_in.open(image_file) as source:
                                    z_out.writestr(os.path.basename(image_file), source.read())
                                matches_found += 1
                                break
            
            # Mise à jour finale
            progress_bar.progress(1.0)
            status_text.text(f"Traitement terminé. {matches_found} correspondances trouvées.")
            
            # Afficher les statistiques
            st.success(f"Traitement terminé avec succès!")
            st.metric("EANs traités", len(eans))
            st.metric("Correspondances trouvées", matches_found)
            
            # Lien de téléchargement
            st.markdown("### Télécharger les résultats")
            st.markdown(get_binary_file_downloader_html(output_zip_path, 'Résultats (ZIP)'), unsafe_allow_html=True)
            
            # Astuces pour le téléchargement sur certains navigateurs
            st.info("Si le lien de téléchargement ne fonctionne pas, essayez de faire un clic droit et 'Enregistrer le lien sous...'")

# Informations supplémentaires
st.markdown("---")
st.markdown("### Comment utiliser cette application")
st.markdown("""
1. **Fichier Excel**: Le fichier doit contenir une colonne avec les codes EAN.
2. **Archive ZIP**: L'archive doit contenir les images au format `XXXXXX_1.png` ou `XXXXXX_1.jpg` où XXXXXX est le code EAN.
3. **Résultat**: Un fichier ZIP contenant uniquement les images correspondant aux codes EAN trouvés dans le fichier Excel.
""")

# Footer
st.markdown("---")
st.markdown("Application créée avec Streamlit")
