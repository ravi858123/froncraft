# FontCraft

Een kleine Windows-app waarmee je:

1. Je eigen lettertype (`.ttf` of `.otf`) uploadt vanaf je computer.
2. Tekst typt en meteen een voorbeeld ziet in dat lettertype.
3. Het resultaat opslaat als **PNG**, **JPEG/JPG**, **SVG** of **PDF**.

## Lokaal draaien (zonder exe)

```bash
pip install -r requirements.txt
python app.py
```

## Zelf een .exe bouwen (lokaal, op Windows)

```bash
pip install -r requirements.txt
pyinstaller --noconfirm --onefile --windowed --name "FontCraft" app.py
```

De exe komt te staan in de map `dist/FontCraft.exe`.

## Automatisch bouwen via GitHub Actions

Dit repository bevat `.github/workflows/build.yml`. Zodra je dit naar
GitHub pusht, bouwt GitHub Actions automatisch een Windows `.exe`:

- Bij elke push naar de `main`-branch.
- Bij elke pull request naar `main`.
- Handmatig via **Actions → Build Windows EXE → Run workflow**.
- Bij het aanmaken van een tag zoals `v1.0.0` wordt er bovendien
  automatisch een **GitHub Release** aangemaakt met de exe erin.

### Zo gebruik je het

1. Maak een nieuwe (lege) GitHub-repository aan.
2. Push deze bestanden ernaartoe:

   ```bash
   git init
   git add .
   git commit -m "Eerste versie van FontCraft"
   git branch -M main
   git remote add origin https://github.com/<jouw-gebruikersnaam>/<repo-naam>.git
   git push -u origin main
   ```

3. Ga naar de **Actions**-tab van je repository op GitHub. De workflow
   start automatisch. Zodra hij klaar is (groen vinkje), staat de exe
   klaar als "artifact" onderaan de workflow-run, om te downloaden.
4. (Optioneel) Wil je een officiele release met exe? Maak dan een tag:

   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

## Projectstructuur

```
font-text-exporter/
├── app.py                       # De hoofdapplicatie (tkinter GUI)
├── requirements.txt              # Python-afhankelijkheden
├── README.md
└── .github/
    └── workflows/
        └── build.yml              # GitHub Actions workflow voor de .exe
```

## Opmerkingen

- SVG-exports embedden het lettertype als base64 (`@font-face`), zodat
  de tekst er in elke moderne browser/SVG-viewer identiek uitziet.
- PDF-exports proberen het lettertype rechtstreeks in te bedden via
  ReportLab. Lukt dat niet (bv. bij sommige OTF-varianten), dan valt
  de app terug op een standaardlettertype en krijg je geen foutmelding
  die de export blokkeert.
- Geüploade lettertypes worden lokaal bewaard in
  `%USERPROFILE%\.font_text_exporter\fonts`, zodat ze na herstart van
  de app weer beschikbaar zijn.
