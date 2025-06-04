# KeyLock API Wallet

KeyLock is a Python tool and Gradio application to securely embed and extract API key-value pairs (or any secret textual data) within PNG images. It uses LSB (Least Significant Bit) steganography for hiding data and AES-256-GCM encryption for securing it.

Current Version: 1.0.0

## Features

- Embed secret data (key-value pairs) into PNG images.
- Extract secret data from these steganography-enhanced PNGs.
- AES-256-GCM encryption with password-derived keys (PBKDF2-SHA256).
- Optional visual overlay on the image indicating data presence and (optionally) key names.
- Gradio web interface for easy use.

## Installation

### Prerequisites
- Python 3.8 or newer.

### From GitHub
You can install the package directly from GitHub:

```bash
pip install git+https://github.com/user/KeyLock-API-Wallet.git
```

### For Development
If you want to contribute or modify the code:
1. Clone the repository:
   ```bash
   git clone https://github.com/user/KeyLock-API-Wallet.git
   cd KeyLock-API-Wallet
   ```
2. Create and activate a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venvScriptsactivate
   ```
3. Install in editable mode:
   ```bash
   pip install -e .
   ```

This installs all dependencies listed in `requirements.txt`.

## Usage

After installation, you can run the Gradio application using the command-line script:

```bash
keylock-app
```

This will start a local web server, and you can access the application through your browser (typically at `http://127.0.0.1:7860` or a similar address shown in the console).

Alternatively, if installed in editable mode or if the package is otherwise in your `PYTHONPATH`, you can run:
```bash
python -m keylock.app
```

### Embedding Data
1. Launch the application and navigate to the "➕ Embed Data" tab.
2. Enter your secret data in `Key:Value` or `Key=Value` format, one entry per line (e.g., `API_KEY:your_secret_value`).
3. Set a strong, unique encryption password. This password is vital for both embedding and extracting data.
4. Choose to "Generate new KeyLock Wallet image" (a default carrier image) or uncheck it to "Upload Your Own (PNG required)".
5. Configure "Visual Markings":
    - Optionally, check "Show list of key names" to display the keys on the image overlay.
    - A "KeyLock: Data Embedded" title bar will always be part of the overlay.
6. Provide a "Base Name for Downloaded Stego Image" (e.g., `my_api_keys`). The `.png` extension will be added.
7. Click "Embed Secrets ➕".
8. A preview of the stego image will appear.
9. Download the resulting PNG image using the "Download Your KeyLock Image (PNG)" button.

### Extracting Data
1. Go to the "➖ Extract Data" tab.
2. Upload the KeyLock PNG image (the one you downloaded after embedding). It must be the original, unmodified PNG.
3. Enter the exact decryption password used during the embedding process.
4. Click "Extract Secrets ➖".
5. The extracted data (typically in JSON format) will be displayed. If decryption fails or data is not valid JSON, raw or hex output may be shown with a warning.

## Important Notes
- **Use Downloaded PNG for Extraction:** Always use the PNG file downloaded directly from the application for extraction. Copy-pasting images from a web browser, re-saving, or re-compressing them (e.g., through social media, image editors) can corrupt or destroy the LSB data.
- **PNG Format is Crucial:** The steganography process relies on the lossless nature of PNGs. Other formats or converted images will likely result in data loss.
- **Password Security:** Use strong, unique passwords. There is no password recovery mechanism; if you forget the password, the data is irrecoverable.
- **Data Capacity:** The amount of data you can hide depends on the pixel dimensions of the carrier image (1 bit per color channel value, 3 bits per pixel). The visual overlay itself modifies pixels before LSB encoding, slightly affecting available capacity. Very large data may not fit in small images.

## License
This project is intended to be licensed under the MIT License. Please add a `LICENSE` file with the MIT License text to the repository.
(Example: Create a `LICENSE` file and paste the text from [https://opensource.org/licenses/MIT](https://opensource.org/licenses/MIT))
