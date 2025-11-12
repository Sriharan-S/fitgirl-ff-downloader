# FitGirl FF Downloader

A GUI application for downloading files from FitGirl Repacks website using FuckingFast.co links.

## Features

- Scrapes FitGirl Repacks pages for download links
- GUI-based file selection
- Progress tracking for downloads
- Resume support for interrupted downloads
- Automatic state management

## Prerequisites

- Python 3.7 or higher
- Internet connection

## Running from Python Source

### 1. Clone the Repository

```bash
git clone https://github.com/Sriharan-S/fitgirl-ff-downloader.git
cd fitgirl-ff-downloader
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the Application

```bash
python main.py
```

## Running from Pre-built Executable

If you don't want to install Python or manage dependencies, you can download and run the pre-built executable.

### 1. Download the Latest Release

1. Go to the [Releases page](https://github.com/Sriharan-S/fitgirl-ff-downloader/releases/tag/latest)
2. Download the appropriate executable for your operating system:
   - **Windows**: `fitgirl-ff-downloader.exe`
   - **Linux**: `fitgirl-ff-downloader` (Linux binary)
   - **macOS**: `fitgirl-ff-downloader` (macOS binary)

### 2. Run the Executable

#### Windows
- Double-click the `fitgirl-ff-downloader.exe` file
- Or run from Command Prompt:
  ```cmd
  fitgirl-ff-downloader.exe
  ```

#### Linux/macOS
- First, make the file executable:
  ```bash
  chmod +x fitgirl-ff-downloader
  ```
- Then run it:
  ```bash
  ./fitgirl-ff-downloader
  ```

## How to Use

1. **Enter the URL**: Paste the FitGirl Repacks page URL in the "Source URL" field
2. **Select Download Location**: Click "Select Folder" to choose where files should be downloaded
3. **Start Processing**: Click "Start Processing" to begin
4. **Select Files**: A dialog will appear with all available files - select which ones you want to download
5. **Monitor Progress**: Watch the progress bar and logs as files download

## Session Resume

The application automatically saves download progress. If you close the application before all downloads complete:
- Your session state is saved in the download folder
- Next time you run the application with the same URL, it will offer to resume from where you left off
- Already downloaded files will be skipped

## Troubleshooting

### Windows Security Warning
When running the executable on Windows, you might see a "Windows protected your PC" warning. This is normal for unsigned executables. Click "More info" and then "Run anyway".

### macOS Security Warning
On macOS, you might need to allow the app in System Preferences > Security & Privacy after the first run attempt.

### Python Module Not Found
If you get a "Module not found" error when running from source:
```bash
pip install --upgrade -r requirements.txt
```

## License

This project is provided as-is for educational purposes.
