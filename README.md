# KeyLock API Wallet

KeyLock is a Python tool and Gradio application designed to securely embed and extract API key-value pairs (or any secret textual data) within PNG images. It leverages LSB (Least Significant Bit) steganography for covertly hiding data and AES-256-GCM encryption for robust security.

Current Version: 1.0.0

## Features

- **Secure Embedding:** Embed secret data (formatted as key-value pairs) into PNG images.
- **Reliable Extraction:** Extract previously embedded secret data from KeyLock-enhanced PNGs.
- **Strong Encryption:** Utilizes AES-256-GCM encryption with password-derived keys (PBKDF2-SHA256) to protect your data.
- **Visual Indicators:** Optionally adds a visual overlay on the carrier image, indicating that data is embedded and, if chosen, displaying the names of the embedded keys.
- **User-Friendly Interface:** Provides an intuitive Gradio web interface for ease of use, accessible through your browser.
- **Portable:** Creates self-contained "wallets" in PNG files that can be easily stored and shared (with caution, considering the sensitivity of the data).

## Installation

This section details how to install the KeyLock API Wallet. A virtual environment is strongly recommended for all Python projects to manage dependencies and avoid conflicts.

### Prerequisites

- Python 3.8 or newer.
- `pip` (Python package installer).

### 1. Setting up a Virtual Environment (Recommended)

Before installing, create and activate a virtual environment:

   \```bash
   # Navigate to your preferred projects directory
   # cd /path/to/your/projects

   # Create the virtual environment (e.g., named 'keylock_env')
   python -m venv keylock_env

   # Activate the virtual environment:
   # On macOS and Linux:
   source keylock_env/bin/activate
   # On Windows (Command Prompt/PowerShell):
   .\keylock_env\Scripts\activate
   \```
   Your command prompt should now indicate that the virtual environment is active (e.g., `(keylock_env) $`).

### 2. Installation Options

Choose one of the following methods to install KeyLock:

#### Option A: Install Directly from GitHub (for Users)

This is the simplest way to install the latest version for regular use:

   \```bash
   pip install git+https://github.com/user/KeyLock-API-Wallet.git
   \```

#### Option B: Install from a Local Clone (for Users or Developers)

If you have cloned the repository or downloaded the source code:

   1.  Clone the repository (if you haven't already):
       \```bash
       git clone https://github.com/user/KeyLock-API-Wallet.git
       cd KeyLock-API-Wallet
       \```
   2.  Install the package (ensure your virtual environment is active):
       \```bash
       pip install .
       \```

#### Option C: Install in Editable Mode (for Developers)

This method is ideal if you plan to modify the KeyLock source code. Changes you make to the code will be immediately effective without needing to reinstall.

   1.  Clone the repository (if you haven't already):
       \```bash
       git clone https://github.com/user/KeyLock-API-Wallet.git
       cd KeyLock-API-Wallet
       \```
   2.  Install in editable mode (ensure your virtual environment is active):
       \```bash
       pip install -e .
       \```

All installation methods will automatically install the required dependencies listed in `requirements.txt` (Gradio, Pillow, cryptography, numpy).

## Running the KeyLock Application

Once KeyLock is installed, you can launch the Gradio web interface using one of the following methods. Ensure your virtual environment (e.g., `keylock_env`) is active if you installed it there.

### Method 1: Using the Command-Line Entry Point (Recommended)

The `setup.py` file configures a command-line script called `keylock-app`. This is the most convenient way to run the application after any successful `pip install` (from GitHub, local clone, or editable mode).

   Simply type the following in your terminal:
   \```bash
   keylock-app
   \```

   The application will start, and you'll see output similar to this in your terminal:
   \```
   Running on local URL:  http://127.0.0.1:7860
   # Or a similar URL if port 7860 is in use.
   \```
   Open the provided URL in your web browser to access the KeyLock interface.

### Method 2: Running as a Python Module

This method is useful if you've installed in editable mode or if the `keylock` package is directly in your Python path (e.g., you are in the `KeyLock-API-Wallet` directory after cloning and have not installed it with `pip install .` yet, but the virtual environment has the dependencies).

   Execute the following command in your terminal:
   \```bash
   python -m keylock.app
   \```
   This directly invokes the `main()` function within the `keylock/app.py` module. You will see the same Gradio startup messages as with Method 1.

### Accessing the Interface

After starting the application using either method, open the URL displayed in your terminal (usually `http://127.0.0.1:7860`) in your web browser.

## Using the KeyLock Interface

### Embedding Data

1.  **Navigate:** Launch the application and go to the "➕ Embed Data" tab.
2.  **Input Data:** Enter your secret data in the "Secret Data (Key:Value Pairs)" textbox. Use the format `API_KEY:your_secret_value` or `API_KEY=your_secret_value`. Each entry should be on a new line.
3.  **Set Password:** Create and enter a strong, unique "Encryption Password". This password is critical for securing your data and will be required to extract it later. **Store this password securely; if lost, the data is irrecoverable.**
4.  **Carrier Image:**
    *   **Generate:** Keep "Generate new KeyLock Wallet image" checked to use a default, visually distinct carrier image.
    *   **Upload:** Uncheck this option to "Upload Your Own (PNG required)". Select a PNG image from your system.
5.  **Visual Markings:**
    *   **Key List:** Optionally, check "Show list of key names" to display the names of your embedded keys as part of the visual overlay on the top-left of the image. This appears below the "KeyLock: Data Embedded" title bar.
    *   A "KeyLock: Data Embedded" title bar will always be present in the overlay.
6.  **Output Filename:** Specify a "Base Name for Downloaded Stego Image" (e.g., `my_project_secrets`). The `.png` extension will be automatically appended.
7.  **Embed:** Click the "Embed Secrets ➕" button.
8.  **Preview & Download:** A preview of the final steganographic image will be shown. Use the "Download Your KeyLock Image (PNG)" button to save the image to your computer.

### Extracting Data

1.  **Navigate:** Go to the "➖ Extract Data" tab.
2.  **Upload Image:** Upload the KeyLock PNG image from which you want to extract data. This must be the original, unmodified PNG file generated by the KeyLock application.
3.  **Enter Password:** Input the exact "Decryption Password" that was used when the data was originally embedded into this image.
4.  **Extract:** Click the "Extract Secrets ➖" button.
5.  **View Data:** The "Extracted Secret Data" textbox will display the recovered data, typically in JSON format. If decryption fails due to an incorrect password or data corruption, or if the data wasn't originally JSON, an error message or a raw/hex representation of the decrypted bytes will be shown along with a status message.

## Important Notes & Best Practices

-   **Use Original PNGs:** For extraction, **always use the .png file downloaded directly from the KeyLock application**. Copy-pasting images from web browsers, re-saving them through image editors, or sending them through platforms that re-compress images (like many social media sites) can alter or destroy the LSB data, making extraction impossible.
-   **PNG Format is Essential:** The steganography technique relies on the lossless nature of the PNG format. Attempting to use other image formats or images converted to/from other formats will likely result in data loss.
-   **Password Security:**
    *   Use strong, unique passwords for each KeyLock image.
    *   **There is no password recovery mechanism.** If you forget the password, the data embedded with that password is permanently inaccessible.
    *   Store your passwords securely using a password manager.
-   **Data Capacity:** The amount of data that can be hidden is limited by the pixel dimensions of the carrier image (1 bit per color channel value, meaning 3 bits per pixel before considering the header). The visual overlay itself modifies some pixels before the LSB encoding process, which slightly reduces the available capacity. Embedding very large amounts of data may require a larger carrier image.
-   **Sensitivity of Data:** While KeyLock uses strong encryption, remember that steganography is about hiding the *existence* of data. If the image itself is compromised and an attacker knows to look for LSB data, the security relies solely on the strength of your encryption password. Treat KeyLock PNGs containing sensitive information with the same care you would treat any encrypted file.

## License

This project is intended to be licensed under the MIT License. Please ensure a `LICENSE` file with the MIT License text is present in the repository.
(Example: Create a `LICENSE` file and paste the text from [https://opensource.org/licenses/MIT](https://opensource.org/licenses/MIT))
