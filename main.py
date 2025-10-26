import os
import re
import requests
import threading
import queue  # Added for thread-safe communication
import json  # --- NEW: For saving state
import hashlib  # --- NEW: For hashing URL to create a unique state file
from bs4 import BeautifulSoup
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext


# --- New Selection Dialog Class ---

class SelectionDialog(tk.Toplevel):
    """A modal dialog to select which files to download."""

    def __init__(self, parent, files, selection_queue):
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        self.title("Select Files to Download")
        self.geometry("600x400")

        self.files = files
        self.queue = selection_queue
        self.vars = []  # To hold the BooleanVar for each checkbox

        # --- Top frame for controls ---
        control_frame = ttk.Frame(self)
        control_frame.pack(pady=5)

        ttk.Button(control_frame, text="Select All", command=self.select_all).pack(side="left", padx=5)
        ttk.Button(control_frame, text="Deselect All", command=self.deselect_all).pack(side="left", padx=5)

        # --- Frame for scrollable checkbox list ---
        list_frame = ttk.Frame(self, relief="sunken", borderwidth=1)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.canvas = tk.Canvas(list_frame)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # --- Populate the list ---
        for file_info in self.files:
            var = tk.BooleanVar(value=True)  # Default to checked
            self.vars.append(var)
            chk = ttk.Checkbutton(self.scrollable_frame, text=file_info['name'], variable=var)
            chk.pack(anchor="w", padx=10, pady=2)

        # --- Bottom frame for OK/Cancel ---
        bottom_frame = ttk.Frame(self)
        bottom_frame.pack(pady=10)

        ttk.Button(bottom_frame, text="OK", command=self.on_ok).pack(side="left", padx=10)
        ttk.Button(bottom_frame, text="Cancel", command=self.on_cancel).pack(side="right", padx=10)

        # Handle window close button
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

        # Wait for the window to be visible before grabbing
        self.wait_visibility()
        self.grab_set()
        self.focus_set()

    def select_all(self):
        for var in self.vars:
            var.set(True)

    def deselect_all(self):
        for var in self.vars:
            var.set(False)

    def on_ok(self):
        """Collect selected files and put them in the queue."""
        selected_files = []
        for i, var in enumerate(self.vars):
            if var.get():
                selected_files.append(self.files[i])

        self.queue.put(selected_files)
        self.destroy()

    def on_cancel(self):
        """Put an empty list in the queue to signal cancellation."""
        self.queue.put([])
        self.destroy()


# --- Main Application Class ---

class DownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Web Page Link Downloader")
        self.root.geometry("800x600")

        # --- Class Variables ---
        self.download_folder = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Downloads"))

        self.headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language': 'en-US,en;q=0.5',
            'referer': 'https://fitgirl-repacks.site/',
            'sec-ch-ua': '"Brave";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        }

        # --- Create GUI Widgets ---
        self.create_widgets()

    def create_widgets(self):
        # --- Frame 1: Source Selection ---
        source_frame = ttk.LabelFrame(self.root, text="Source URL", padding=(10, 5))
        source_frame.pack(fill="x", padx=10, pady=5)

        self.url_entry = ttk.Entry(source_frame, width=60, state="normal")  # Enabled by default
        self.url_entry.pack(side="left", fill="x", expand=True, padx=10)

        # --- Frame 2: Download Location ---
        folder_frame = ttk.LabelFrame(self.root, text="Download Location", padding=(10, 5))
        folder_frame.pack(fill="x", padx=10, pady=5)

        folder_label = ttk.Label(folder_frame, textvariable=self.download_folder, relief="sunken", padding=(5, 2))
        folder_label.pack(side="left", fill="x", expand=True, padx=(0, 10))

        folder_button = ttk.Button(folder_frame, text="Select Folder", command=self.select_folder)
        folder_button.pack(side="right")

        # --- Frame 3: Controls ---
        control_frame = ttk.Frame(self.root, padding=(10, 5))
        control_frame.pack(fill="x", padx=10)

        self.start_button = ttk.Button(control_frame, text="Start Processing", command=self.start_processing_thread)
        self.start_button.pack(pady=5)

        # --- Frame 4: Progress Bar ---
        progress_frame = ttk.LabelFrame(self.root, text="Download Progress", padding=(10, 5))
        progress_frame.pack(fill="x", padx=10, pady=5)

        self.status_label = ttk.Label(progress_frame, text="Waiting for download...")
        self.status_label.pack(fill="x", pady=(0, 5))

        self.progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", length=100, mode="determinate")
        self.progress_bar.pack(fill="x")

        # --- Frame 5: Logging Output ---
        log_frame = ttk.LabelFrame(self.root, text="Logs", padding=(10, 5))
        log_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        self.log_text = scrolledtext.ScrolledText(log_frame, state="disabled", height=15, wrap=tk.WORD,
                                                  font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)

        # Configure color tags for logging
        self.log_text.tag_config("timestamp", foreground="#888888")
        self.log_text.tag_config("success", foreground="#009900")
        self.log_text.tag_config("error", foreground="#CC0000")
        self.log_text.tag_config("done", foreground="#CC00CC")
        self.log_text.tag_config("warning", foreground="#FF8C00")
        self.log_text.tag_config("info", foreground="#0000FF")
        self.log_text.tag_config("normal", foreground="black")

    # --- GUI Callback Functions ---

    def select_folder(self):
        """Opens a dialog to select a download folder."""
        folder = filedialog.askdirectory(parent=self.root, initialdir=self.download_folder.get())
        if folder:
            self.download_folder.set(folder)

    def log_to_gui(self, message, obj, tag="info"):
        """
        Safely inserts a formatted log message into the GUI Text widget
        from any thread using root.after().
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        tag_prefix = tag.upper().ljust(4)
        self.root.after(0, self._insert_log_text, timestamp, tag_prefix, message, obj, tag)

    def _insert_log_text(self, timestamp, tag_prefix, message, obj, tag):
        """Internal helper to modify the Text widget (must run on main thread)."""
        try:
            self.log_text.config(state="normal")
            self.log_text.insert(tk.END, f"{timestamp} » ", "timestamp")
            self.log_text.insert(tk.END, f"{tag_prefix} • ", tag)
            self.log_text.insert(tk.END, f"{message} : {obj}\n", "normal")
            self.log_text.config(state="disabled")
            self.log_text.see(tk.END)  # Auto-scroll
        except Exception as e:
            print(f"Error logging to GUI: {e}")

    def update_progress(self, current_bytes, total_bytes, filename):
        """Safely updates the progress bar and status label from any thread."""
        percent = 0
        status_text = f"Downloading {filename[:35]}{'...' if len(filename) > 35 else ''}..."

        if total_bytes > 0:
            percent = (current_bytes / total_bytes) * 100
            status_text += f" ({current_bytes / 1024 / 1024:.1f}MB / {total_bytes / 1024 / 1024:.1f}MB)"

        self.root.after(0, self._set_progress, percent, status_text)

    def _set_progress(self, percent, status_text):
        """Internal helper to modify progress widgets (must run on main thread)."""
        self.progress_bar['value'] = percent
        self.status_label.config(text=status_text)

    def clear_progress(self):
        """Safely resets the progress bar and label."""
        self.root.after(0, self._set_progress, 0, "Download complete. Waiting for next file...")

    def show_error(self, title, message):
        """Safely shows a messagebox error from any thread."""
        self.root.after(0, lambda: messagebox.showerror(title, message, parent=self.root))

    # --- Threading and Core Logic ---

    def start_processing_thread(self):
        """
        Validates input and starts the main processing logic in a
        separate thread to keep the GUI responsive.
        """
        self.start_button.config(state="disabled", text="Processing...")
        scrape_url = self.url_entry.get()
        download_folder = self.download_folder.get()

        if not download_folder:
            self.show_error("Input Error", "Please select a download folder.")
            self.start_button.config(state="normal", text="Start Processing")
            return

        if not scrape_url:
            self.show_error("Input Error", "Please enter a URL to scrape.")
            self.start_button.config(state="normal", text="Start Processing")
            return

        self.selection_queue = queue.Queue()

        self.log_to_gui("Starting processing...", "", "info")
        worker_thread = threading.Thread(
            target=self.process_links,
            args=(scrape_url, download_folder, self.selection_queue),
            daemon=True
        )
        worker_thread.start()

    def process_links(self, scrape_url, download_folder, selection_queue):
        """
        THE WORKER THREAD FUNCTION
        Handles link discovery, state management, and downloading.
        """

        # --- NEW: State File Logic ---
        # Create a unique, "hidden" state file based on the scrape URL
        url_hash = hashlib.sha1(scrape_url.encode()).hexdigest()
        state_file = os.path.join(download_folder, f".download_state_{url_hash}.json")
        links_to_discover = []
        # --- End NEW ---

        try:
            # --- PHASE 1: DISCOVERY (with Resume Logic) ---
            filter_prefix = "https://fuckingfast.co/"

            # --- NEW: Check for existing state file ---
            if os.path.exists(state_file):
                try:
                    with open(state_file, 'r') as f:
                        links_to_discover = json.load(f)
                    if links_to_discover:
                        self.log_to_gui(f"Resuming previous session. Found {len(links_to_discover)} remaining links.",
                                        os.path.basename(state_file), "info")
                    else:
                        self.log_to_gui("State file was empty. Starting fresh scrape.", os.path.basename(state_file),
                                        "warning")
                        # Force re-scrape by falling through
                except Exception as e:
                    self.log_to_gui(
                        f"Error reading state file '{os.path.basename(state_file)}'. Starting fresh scrape.", str(e),
                        "error")
                    links_to_discover = []  # Ensure list is empty to trigger scrape

            if not links_to_discover:
                self.log_to_gui("No previous session found. Starting fresh scrape...", scrape_url, "info")
                links_to_discover = self.scrape_links(scrape_url, filter_prefix)
                if links_to_discover:
                    self.log_to_gui(f"Scrape complete. Found {len(links_to_discover)} links.", "Saving state...",
                                    "info")
                    self.save_state_file(state_file, links_to_discover)
                else:
                    self.log_to_gui("No matching links found to process.", "", "warning")
                    return  # Stop if scraping found nothing
            # --- End NEW ---

            self.log_to_gui(f"Discovering file details for {len(links_to_discover)} links...", "", "info")

            discovered_files = []
            # --- MODIFIED: Use links_to_discover list ---
            for i, link in enumerate(links_to_discover):
                self.log_to_gui(f"Discovering file {i + 1}/{len(links_to_discover)}...", f"{link[:50]}...", "info")
                try:
                    response = requests.get(link, headers=self.headers)
                    if response.status_code != 200:
                        self.log_to_gui(f"Failed To Fetch Page", f"Status: {response.status_code} for {link}", "error")
                        continue

                    soup = BeautifulSoup(response.text, 'html.parser')
                    meta_title = soup.find('meta', attrs={'name': 'title'})

                    if meta_title and meta_title.get('content'):
                        file_name = meta_title['content']
                        file_name = re.sub(r'[<>:"/\\|?*]', '_', file_name)
                    else:
                        file_name = f"download_{datetime.now().strftime('%Y%m%d%H%M%S')}_{i}"
                        self.log_to_gui("Could not find meta title, using default filename", file_name, "warning")

                    script_tags = soup.find_all('script')
                    download_function = None
                    for script in script_tags:
                        if script.string and 'function download' in script.string:
                            download_function = script.string
                            break

                    if download_function:
                        match = re.search(r'window\.open\(["\'](https?://[^\s"\'\)]+)', download_function)
                        if match:
                            download_url = match.group(1)
                            discovered_files.append({
                                'name': file_name,
                                'url': download_url,
                                'page_link': link  # --- IMPORTANT: We store this to update the state file
                            })
                        else:
                            self.log_to_gui("No Download URL Found in download function for", link, "error")
                    else:
                        self.log_to_gui("Download Function Not Found on page", link, "error")
                except Exception as e:
                    self.log_to_gui(f"Error discovering link {link}", str(e), "error")

            if not discovered_files:
                self.log_to_gui("Discovery finished, but no valid files were found.", "", "error")
                # --- NEW: Clean up state file if discovery fails for all links ---
                if os.path.exists(state_file):
                    os.remove(state_file)
                self.log_to_gui("Removed state file due to discovery failure.", "", "warning")
                return

            # --- PHASE 2: USER SELECTION ---
            self.log_to_gui(f"Discovery complete. Found {len(discovered_files)} valid files.",
                            "Waiting for user selection...", "done")

            self.root.after(0, lambda: SelectionDialog(self.root, discovered_files, selection_queue))
            selected_files = selection_queue.get()

            # --- PHASE 3: DOWNLOADING ---
            if not selected_files:
                self.log_to_gui("Download cancelled by user.", "State file with remaining links is preserved.",
                                "warning")
                return

            self.log_to_gui(f"User selected {len(selected_files)} of {len(discovered_files)} files to download.", "",
                            "info")

            for i, file_info in enumerate(selected_files):
                self.log_to_gui(f"Downloading file {i + 1}/{len(selected_files)}...", file_info['name'], "info")
                try:
                    dl_success = self.download_file_gui(file_info['url'], download_folder, file_info['name'])

                    if dl_success:
                        # --- NEW: Update state file on success ---
                        self.log_to_gui("Updating session file (removing downloaded link)...",
                                        os.path.basename(state_file), "info")
                        if file_info['page_link'] in links_to_discover:
                            links_to_discover.remove(file_info['page_link'])
                            self.save_state_file(state_file, links_to_discover)
                        else:
                            self.log_to_gui("Link not in state list (already processed?)", file_info['page_link'],
                                            "warning")
                        # --- End NEW ---

                except Exception as e:
                    self.log_to_gui(f"Error processing link {file_info['page_link']}", str(e), "error")

            self.log_to_gui("Processing complete for selected files.", "", "done")

            # --- NEW: Final cleanup ---
            if not links_to_discover:
                self.log_to_gui("All links in session processed.", "Removing session file.", "done")
                try:
                    if os.path.exists(state_file):
                        os.remove(state_file)
                except Exception as e:
                    self.log_to_gui("Could not remove session file.", str(e), "warning")
            else:
                self.log_to_gui(f"{len(links_to_discover)} links remain in session file for next time.",
                                os.path.basename(state_file), "info")
            # --- End NEW ---

        except Exception as e:
            self.log_to_gui("An unexpected error occurred in the worker thread", str(e), "error")
            self.show_error("Worker Thread Error", f"An error occurred: {e}")

        finally:
            self.root.after(0, lambda: self.start_button.config(state="normal", text="Start Processing"))
            self.root.after(0, lambda: self.status_label.config(text="Finished. Ready to start again."))

    # --- NEW: Helper function to save state ---
    def save_state_file(self, state_file_path, links_list):
        """Saves the current list of pending links to the state file."""
        try:
            with open(state_file_path, 'w') as f:
                json.dump(links_list, f, indent=2)
        except Exception as e:
            self.log_to_gui(f"Failed to save state file!", f"{os.path.basename(state_file_path)}: {e}", "error")

    # --- Helper Functions (Called by Worker Thread) ---

    def scrape_links(self, target_url, filter_prefix):
        """Scrapes a webpage for links, logging to the GUI."""
        self.log_to_gui("Scraping URL for links", target_url, "info")
        try:
            response = requests.get(target_url, headers=self.headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            self.log_to_gui("Failed to retrieve webpage for scraping", str(e), "error")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        found_links = [
            a['href'] for a in soup.find_all('a', href=True)
            if a['href'].startswith(filter_prefix)
        ]

        if not found_links:
            self.log_to_gui("No matching links found on the page with prefix", filter_prefix, "warning")
        else:
            self.log_to_gui(f"Found {len(found_links)} matching links", "", "success")

        # --- NEW: Return unique links to prevent duplicates in state file ---
        unique_links = list(dict.fromkeys(found_links))
        if len(unique_links) < len(found_links):
            self.log_to_gui(f"Removed {len(found_links) - len(unique_links)} duplicate links.", "", "info")

        return unique_links

    def download_file_gui(self, download_url, output_folder, file_label):
        """
        Downloads a file, updating the GUI progress bar.
        It determines the filename from response headers or URL.
        Returns True on success, False on failure.
        """
        try:
            response = requests.get(download_url, stream=True, headers=self.headers)

            if response.status_code == 200:
                file_name = file_label
                content_disposition = response.headers.get('content-disposition')
                if content_disposition:
                    match = re.search(r'filename="?([^"]+)"?', content_disposition)
                    if match:
                        file_name = match.group(1)
                else:
                    parsed_url_path = download_url.split('?')[0].split('#')[0]
                    url_filename = parsed_url_path.split('/')[-1]
                    if url_filename:
                        file_name = url_filename

                file_name = re.sub(r'[<>:"/\\|?*]', '_', file_name)

                if not file_name or file_name.endswith('.'):
                    file_name = file_label + "_download"
                    self.log_to_gui("Could not determine filename, using label", file_name, "warning")

                output_path = os.path.join(output_folder, file_name)
                total_size = int(response.headers.get('content-length', 0))
                block_size = 8192
                downloaded_so_far = 0

                self.update_progress(0, total_size, file_name)

                with open(output_path, 'wb') as f:
                    for data in response.iter_content(block_size):
                        f.write(data)
                        downloaded_so_far += len(data)
                        self.update_progress(downloaded_so_far, total_size, file_name)

                self.log_to_gui(f"Successfully Downloaded File", os.path.basename(output_path), "success")
                self.clear_progress()
                return True
            else:
                self.log_to_gui(f"Failed To Download File (Status: {response.status_code})",
                                f"{file_label} from {download_url}", "error")
                self.clear_progress()
                return False
        except Exception as e:
            self.log_to_gui(f"Failed To Download File '{file_label}'", str(e), "error")
            self.clear_progress()
            return False


# --- Main execution ---
if __name__ == "__main__":
    root = tk.Tk()
    app = DownloaderApp(root)
    root.mainloop()
