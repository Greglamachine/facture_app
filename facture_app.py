import streamlit as st
import pandas as pd
import pytesseract
from pdf2image import convert_from_bytes
from io import BytesIO
from datetime import datetime
import tempfile
from lxml import etree

st.title("Générateur de fichier de règlement à partir de factures")

factures = []
total_lignes = []

uploaded_files = st.file_uploader("Importe tes factures (PDF ou image)", type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded_files:
    for file in uploaded_files:
        st.subheader(f"Analyse de {file.name}")

        if file.name.endswith(".pdf"):
            images = convert_from_bytes(file.read())
            image = images[0]
        else:
            image = file

        text = pytesseract.image_to_string(image)

        montant = ""
        ref = ""
        iban = ""

        if "TTC" in text:
            montant = text.split("TTC")[-1].split(" ")[0].strip()

        for line in text.splitlines():
            if "FR76" in line or "IBAN" in line:
                iban = line.strip()
            if "Facture" in line or "Réf" in line:
                ref = line.strip()

        fournisseur = st.text_input(f"Nom du fournisseur ({file.name})", value="")
        montant = st.text_input(f"Montant TTC ({file.name})", value=montant)
        ref = st.text_input(f"Référence facture ({file.name})", value=ref)
        iban = st.text_input(f"IBAN ({file.name})", value=iban)
        bic = st.text_input(f"BIC ({file.name})", value="")
        date_paiement = st.date_input(f"Date de paiement ({file.name})", value=datetime.today())

        total_lignes.append({
            "Fournisseur": fournisseur,
            "Réf. Facture": ref,
            "Montant TTC": montant,
            "IBAN": iban,
            "BIC": bic,
            "Date Paiement": date_paiement.strftime("%Y-%m-%d")
        })

if total_lignes and st.button("Générer le fichier Excel"):
    df = pd.DataFrame(total_lignes)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        df.to_excel(tmp.name, index=False)
        tmp.seek(0)
        st.success("Fichier Excel généré avec succès !")
        st.download_button("Télécharger le fichier Excel", data=tmp.read(), file_name="reglements_factures.xlsx")

if total_lignes and st.button("Générer le fichier XML (SEPA pain.001)"):
    nsmap = {None: "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"}
    Document = etree.Element("Document", nsmap=nsmap)
    CstmrCdtTrfInitn = etree.SubElement(Document, "CstmrCdtTrfInitn")

    GrpHdr = etree.SubElement(CstmrCdtTrfInitn, "GrpHdr")
    etree.SubElement(GrpHdr, "MsgId").text = "BATCH_PAYMENT"
    etree.SubElement(GrpHdr, "CreDtTm").text = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    etree.SubElement(GrpHdr, "NbOfTxs").text = str(len(total_lignes))
    total_sum = sum([float(f["Montant TTC"]) for f in total_lignes if f["Montant TTC"].replace('.', '', 1).isdigit()])
    etree.SubElement(GrpHdr, "CtrlSum").text = str(total_sum)
    InitgPty = etree.SubElement(GrpHdr, "InitgPty")
    etree.SubElement(InitgPty, "Nm").text = "Nom_Emetteur"

    PmtInf = etree.SubElement(CstmrCdtTrfInitn, "PmtInf")
    etree.SubElement(PmtInf, "PmtInfId").text = "BATCH_001"
    etree.SubElement(PmtInf, "PmtMtd").text = "TRF"
    etree.SubElement(PmtInf, "BtchBookg").text = "true"
    etree.SubElement(PmtInf, "ReqdExctnDt").text = datetime.today().strftime("%Y-%m-%d")

    Dbtr = etree.SubElement(PmtInf, "Dbtr")
    etree.SubElement(Dbtr, "Nm").text = "Nom_Emetteur"
    DbtrAcct = etree.SubElement(PmtInf, "DbtrAcct")
    DbtrAcct_Id = etree.SubElement(DbtrAcct, "Id")
    etree.SubElement(DbtrAcct_Id, "IBAN").text = "FR7630004006950002160341716"
    DbtrAgt = etree.SubElement(PmtInf, "DbtrAgt")
    DbtrAgt_FinInstnId = etree.SubElement(DbtrAgt, "FinInstnId")
    etree.SubElement(DbtrAgt_FinInstnId, "BIC").text = "BNPAFRPPXXX"

    for line in total_lignes:
        CdtTrfTxInf = etree.SubElement(PmtInf, "CdtTrfTxInf")
        PmtId = etree.SubElement(CdtTrfTxInf, "PmtId")
        etree.SubElement(PmtId, "EndToEndId").text = line["Réf. Facture"]

        Amt = etree.SubElement(CdtTrfTxInf, "Amt")
        InstdAmt = etree.SubElement(Amt, "InstdAmt", Ccy="EUR")
        InstdAmt.text = line["Montant TTC"]

        CdtrAgt = etree.SubElement(CdtTrfTxInf, "CdtrAgt")
        CdtrAgt_FinInstnId = etree.SubElement(CdtrAgt, "FinInstnId")
        etree.SubElement(CdtrAgt_FinInstnId, "BIC").text = line["BIC"]

        Cdtr = etree.SubElement(CdtTrfTxInf, "Cdtr")
        etree.SubElement(Cdtr, "Nm").text = line["Fournisseur"]
        CdtrAcct = etree.SubElement(CdtTrfTxInf, "CdtrAcct")
        CdtrAcct_Id = etree.SubElement(CdtrAcct, "Id")
        etree.SubElement(CdtrAcct_Id, "IBAN").text = line["IBAN"]

        RmtInf = etree.SubElement(CdtTrfTxInf, "RmtInf")
        etree.SubElement(RmtInf, "Ustrd").text = line["Réf. Facture"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp_xml:
        etree.ElementTree(Document).write(tmp_xml.name, pretty_print=True, xml_declaration=True, encoding="UTF-8")
        tmp_xml.seek(0)
        st.success("Fichier XML généré avec succès !")
        st.download_button("Télécharger le fichier XML", data=tmp_xml.read(), file_name="virements_batch.xml")
