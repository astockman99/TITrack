using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace TITrackSetup;

static class Program
{
    [STAThread]
    static void Main()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new SetupForm());
    }
}

public class SetupForm : Form
{
    private TextBox _pathTextBox;
    private Button _browseButton;
    private Button _extractButton;
    private ProgressBar _progressBar;
    private Label _statusLabel;
    private CheckBox _desktopShortcutCheckBox;
    private CheckBox _deleteSelfCheckBox;
    private Panel _completionPanel;
    private Label _completionLabel;
    private Button _openFolderButton;
    private Button _closeButton;

    private string _extractPath;
    private string _downloadUrl;
    private string _latestVersion;
    private bool _extractionComplete = false;

    private const string GitHubApiUrl = "https://api.github.com/repos/astockman99/TITrack/releases/latest";
    private const string AppName = "TITrack";

    public SetupForm()
    {
        InitializeComponent();
        SetDefaultPath();
        _ = FetchLatestReleaseInfo();
    }

    private void InitializeComponent()
    {
        this.Text = "TITrack Setup";
        this.Size = new System.Drawing.Size(500, 320);
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.MaximizeBox = false;
        this.StartPosition = FormStartPosition.CenterScreen;

        // Title label
        var titleLabel = new Label
        {
            Text = "TITrack - Torchlight Infinite Loot Tracker",
            Font = new System.Drawing.Font("Segoe UI", 12, System.Drawing.FontStyle.Bold),
            Location = new System.Drawing.Point(20, 15),
            AutoSize = true
        };
        this.Controls.Add(titleLabel);

        // Subtitle
        var subtitleLabel = new Label
        {
            Text = "Portable extractor - no installation required",
            ForeColor = System.Drawing.Color.Gray,
            Location = new System.Drawing.Point(20, 42),
            AutoSize = true
        };
        this.Controls.Add(subtitleLabel);

        // Extract path label
        var pathLabel = new Label
        {
            Text = "Extract to:",
            Location = new System.Drawing.Point(20, 80),
            AutoSize = true
        };
        this.Controls.Add(pathLabel);

        // Path textbox
        _pathTextBox = new TextBox
        {
            Location = new System.Drawing.Point(20, 100),
            Size = new System.Drawing.Size(350, 23)
        };
        this.Controls.Add(_pathTextBox);

        // Browse button
        _browseButton = new Button
        {
            Text = "Browse...",
            Location = new System.Drawing.Point(380, 99),
            Size = new System.Drawing.Size(80, 25)
        };
        _browseButton.Click += BrowseButton_Click;
        this.Controls.Add(_browseButton);

        // Desktop shortcut checkbox
        _desktopShortcutCheckBox = new CheckBox
        {
            Text = "Create desktop shortcut",
            Location = new System.Drawing.Point(20, 135),
            AutoSize = true
        };
        this.Controls.Add(_desktopShortcutCheckBox);

        // Progress bar
        _progressBar = new ProgressBar
        {
            Location = new System.Drawing.Point(20, 175),
            Size = new System.Drawing.Size(440, 23),
            Style = ProgressBarStyle.Continuous
        };
        this.Controls.Add(_progressBar);

        // Status label
        _statusLabel = new Label
        {
            Text = "Ready to extract",
            Location = new System.Drawing.Point(20, 205),
            Size = new System.Drawing.Size(440, 20)
        };
        this.Controls.Add(_statusLabel);

        // Extract button
        _extractButton = new Button
        {
            Text = "Extract",
            Location = new System.Drawing.Point(190, 235),
            Size = new System.Drawing.Size(100, 30)
        };
        _extractButton.Click += ExtractButton_Click;
        this.Controls.Add(_extractButton);

        // Completion panel (hidden initially)
        _completionPanel = new Panel
        {
            Location = new System.Drawing.Point(20, 70),
            Size = new System.Drawing.Size(440, 160),
            Visible = false
        };

        _completionLabel = new Label
        {
            Text = "Extraction complete!",
            Font = new System.Drawing.Font("Segoe UI", 11, System.Drawing.FontStyle.Bold),
            ForeColor = System.Drawing.Color.Green,
            Location = new System.Drawing.Point(0, 0),
            AutoSize = true
        };
        _completionPanel.Controls.Add(_completionLabel);

        var instructionLabel = new Label
        {
            Text = "TITrack has been extracted. To run the app,\nopen the folder below and run TITrack.exe",
            Location = new System.Drawing.Point(0, 30),
            AutoSize = true
        };
        _completionPanel.Controls.Add(instructionLabel);

        var pathDisplayLabel = new Label
        {
            Name = "pathDisplayLabel",
            Location = new System.Drawing.Point(0, 75),
            AutoSize = true,
            Font = new System.Drawing.Font("Consolas", 9)
        };
        _completionPanel.Controls.Add(pathDisplayLabel);

        _deleteSelfCheckBox = new CheckBox
        {
            Text = "Delete this setup file (no longer needed)",
            Location = new System.Drawing.Point(0, 105),
            AutoSize = true
        };
        _completionPanel.Controls.Add(_deleteSelfCheckBox);

        _openFolderButton = new Button
        {
            Text = "Open Folder",
            Location = new System.Drawing.Point(80, 135),
            Size = new System.Drawing.Size(100, 28)
        };
        _openFolderButton.Click += OpenFolderButton_Click;
        _completionPanel.Controls.Add(_openFolderButton);

        _closeButton = new Button
        {
            Text = "Close",
            Location = new System.Drawing.Point(200, 135),
            Size = new System.Drawing.Size(100, 28)
        };
        _closeButton.Click += CloseButton_Click;
        _completionPanel.Controls.Add(_closeButton);

        this.Controls.Add(_completionPanel);
    }

    private void SetDefaultPath()
    {
        // Default to same directory as setup exe, or C:\TITrack
        string exePath = Application.ExecutablePath;
        string exeDir = Path.GetDirectoryName(exePath) ?? "";

        // If running from Downloads or temp, use C:\TITrack
        if (exeDir.Contains("Downloads", StringComparison.OrdinalIgnoreCase) ||
            exeDir.Contains("Temp", StringComparison.OrdinalIgnoreCase))
        {
            _pathTextBox.Text = @"C:\TITrack";
        }
        else
        {
            _pathTextBox.Text = Path.Combine(exeDir, "TITrack");
        }
    }

    private async Task FetchLatestReleaseInfo()
    {
        try
        {
            _statusLabel.Text = "Checking for latest version...";

            using var client = new HttpClient();
            client.DefaultRequestHeaders.Add("User-Agent", "TITrack-Setup");

            var response = await client.GetStringAsync(GitHubApiUrl);
            using var doc = JsonDocument.Parse(response);
            var root = doc.RootElement;

            _latestVersion = root.GetProperty("tag_name").GetString()?.TrimStart('v') ?? "unknown";

            // Find the windows zip asset
            var assets = root.GetProperty("assets");
            foreach (var asset in assets.EnumerateArray())
            {
                var name = asset.GetProperty("name").GetString() ?? "";
                if (name.EndsWith("-windows.zip", StringComparison.OrdinalIgnoreCase))
                {
                    _downloadUrl = asset.GetProperty("browser_download_url").GetString();
                    break;
                }
            }

            if (string.IsNullOrEmpty(_downloadUrl))
            {
                _statusLabel.Text = "Error: Could not find download URL";
                _extractButton.Enabled = false;
            }
            else
            {
                _statusLabel.Text = $"Ready to extract TITrack v{_latestVersion}";
            }
        }
        catch (Exception ex)
        {
            _statusLabel.Text = $"Error fetching release info: {ex.Message}";
            _extractButton.Enabled = false;
        }
    }

    private void BrowseButton_Click(object? sender, EventArgs e)
    {
        using var dialog = new FolderBrowserDialog
        {
            Description = "Select extraction folder",
            UseDescriptionForTitle = true,
            SelectedPath = _pathTextBox.Text
        };

        if (dialog.ShowDialog() == DialogResult.OK)
        {
            _pathTextBox.Text = dialog.SelectedPath;
        }
    }

    private async void ExtractButton_Click(object? sender, EventArgs e)
    {
        if (string.IsNullOrEmpty(_downloadUrl))
        {
            MessageBox.Show("Download URL not available. Please check your internet connection.",
                "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }

        _extractPath = _pathTextBox.Text;

        if (string.IsNullOrWhiteSpace(_extractPath))
        {
            MessageBox.Show("Please select an extraction path.", "Error",
                MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        // Disable controls during extraction
        _extractButton.Enabled = false;
        _browseButton.Enabled = false;
        _pathTextBox.Enabled = false;
        _desktopShortcutCheckBox.Enabled = false;

        try
        {
            await DownloadAndExtract();

            if (_desktopShortcutCheckBox.Checked)
            {
                CreateDesktopShortcut();
            }

            ShowCompletionPanel();
        }
        catch (Exception ex)
        {
            MessageBox.Show($"Extraction failed: {ex.Message}", "Error",
                MessageBoxButtons.OK, MessageBoxIcon.Error);

            // Re-enable controls
            _extractButton.Enabled = true;
            _browseButton.Enabled = true;
            _pathTextBox.Enabled = true;
            _desktopShortcutCheckBox.Enabled = true;
            _statusLabel.Text = "Extraction failed. Please try again.";
        }
    }

    private async Task DownloadAndExtract()
    {
        var tempZipPath = Path.Combine(Path.GetTempPath(), $"TITrack-{_latestVersion}.zip");

        try
        {
            // Download
            _statusLabel.Text = "Downloading...";
            _progressBar.Value = 0;

            using var client = new HttpClient();
            client.DefaultRequestHeaders.Add("User-Agent", "TITrack-Setup");

            using var response = await client.GetAsync(_downloadUrl, HttpCompletionOption.ResponseHeadersRead);
            response.EnsureSuccessStatusCode();

            var totalBytes = response.Content.Headers.ContentLength ?? -1;
            var downloadedBytes = 0L;

            using (var contentStream = await response.Content.ReadAsStreamAsync())
            using (var fileStream = new FileStream(tempZipPath, FileMode.Create, FileAccess.Write, FileShare.None))
            {
                var buffer = new byte[81920];
                int bytesRead;

                while ((bytesRead = await contentStream.ReadAsync(buffer, 0, buffer.Length)) > 0)
                {
                    await fileStream.WriteAsync(buffer, 0, bytesRead);
                    downloadedBytes += bytesRead;

                    if (totalBytes > 0)
                    {
                        var progress = (int)((downloadedBytes * 100) / totalBytes);
                        _progressBar.Value = Math.Min(progress, 100);
                        var mbDownloaded = downloadedBytes / (1024.0 * 1024.0);
                        var mbTotal = totalBytes / (1024.0 * 1024.0);
                        _statusLabel.Text = $"Downloading... {mbDownloaded:F1} MB / {mbTotal:F1} MB";
                    }
                }
            }

            // Extract
            _statusLabel.Text = "Extracting...";
            _progressBar.Value = 0;

            // Create target directory
            Directory.CreateDirectory(_extractPath);

            // Extract zip (the zip contains a TITrack folder, we want its contents)
            using (var archive = ZipFile.OpenRead(tempZipPath))
            {
                var totalEntries = archive.Entries.Count;
                var extractedEntries = 0;

                foreach (var entry in archive.Entries)
                {
                    // Skip directory entries
                    if (string.IsNullOrEmpty(entry.Name))
                    {
                        extractedEntries++;
                        continue;
                    }

                    // Remove the top-level "TITrack/" prefix if present
                    var relativePath = entry.FullName;
                    if (relativePath.StartsWith("TITrack/", StringComparison.OrdinalIgnoreCase))
                    {
                        relativePath = relativePath.Substring(8);
                    }
                    else if (relativePath.StartsWith("TITrack\\", StringComparison.OrdinalIgnoreCase))
                    {
                        relativePath = relativePath.Substring(8);
                    }

                    var destPath = Path.Combine(_extractPath, relativePath);
                    var destDir = Path.GetDirectoryName(destPath);

                    if (!string.IsNullOrEmpty(destDir))
                    {
                        Directory.CreateDirectory(destDir);
                    }

                    entry.ExtractToFile(destPath, overwrite: true);

                    extractedEntries++;
                    _progressBar.Value = (extractedEntries * 100) / totalEntries;
                    _statusLabel.Text = $"Extracting... {extractedEntries}/{totalEntries} files";
                }
            }

            _progressBar.Value = 100;
            _statusLabel.Text = "Extraction complete!";
            _extractionComplete = true;
        }
        finally
        {
            // Clean up temp file
            try
            {
                if (File.Exists(tempZipPath))
                {
                    File.Delete(tempZipPath);
                }
            }
            catch { /* Ignore cleanup errors */ }
        }
    }

    private void CreateDesktopShortcut()
    {
        try
        {
            var desktopPath = Environment.GetFolderPath(Environment.SpecialFolder.Desktop);
            var shortcutPath = Path.Combine(desktopPath, "TITrack.lnk");
            var targetPath = Path.Combine(_extractPath, "TITrack.exe");

            // Use PowerShell to create shortcut (simpler than COM interop)
            var script = $@"
                $WshShell = New-Object -ComObject WScript.Shell
                $Shortcut = $WshShell.CreateShortcut('{shortcutPath}')
                $Shortcut.TargetPath = '{targetPath}'
                $Shortcut.WorkingDirectory = '{_extractPath}'
                $Shortcut.Description = 'TITrack - Torchlight Infinite Loot Tracker'
                $Shortcut.Save()
            ";

            var psi = new ProcessStartInfo
            {
                FileName = "powershell.exe",
                Arguments = $"-NoProfile -ExecutionPolicy Bypass -Command \"{script.Replace("\"", "\\\"")}\"",
                CreateNoWindow = true,
                UseShellExecute = false
            };

            using var process = Process.Start(psi);
            process?.WaitForExit(5000);
        }
        catch
        {
            // Shortcut creation is optional, don't fail the extraction
        }
    }

    private void ShowCompletionPanel()
    {
        // Hide extraction controls
        _pathTextBox.Visible = false;
        _browseButton.Visible = false;
        _progressBar.Visible = false;
        _desktopShortcutCheckBox.Visible = false;
        _extractButton.Visible = false;

        foreach (Control c in this.Controls)
        {
            if (c is Label label && label.Text == "Extract to:")
            {
                label.Visible = false;
            }
        }

        // Update and show completion panel
        var pathLabel = _completionPanel.Controls["pathDisplayLabel"] as Label;
        if (pathLabel != null)
        {
            pathLabel.Text = _extractPath;
        }

        _statusLabel.Visible = false;
        _completionPanel.Visible = true;
    }

    private void OpenFolderButton_Click(object? sender, EventArgs e)
    {
        try
        {
            var exePath = Path.Combine(_extractPath, "TITrack.exe");
            if (File.Exists(exePath))
            {
                // Open folder and select the exe
                Process.Start("explorer.exe", $"/select,\"{exePath}\"");
            }
            else
            {
                // Just open the folder
                Process.Start("explorer.exe", _extractPath);
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show($"Could not open folder: {ex.Message}", "Error",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private void CloseButton_Click(object? sender, EventArgs e)
    {
        if (_deleteSelfCheckBox.Checked && _extractionComplete)
        {
            // Schedule self-deletion
            try
            {
                var selfPath = Application.ExecutablePath;
                var batchPath = Path.Combine(Path.GetTempPath(), "titrack_cleanup.bat");

                // Create a batch file that waits and then deletes the setup exe
                var batchContent = $@"
@echo off
timeout /t 2 /nobreak > nul
del ""{selfPath}""
del ""{batchPath}""
";
                File.WriteAllText(batchPath, batchContent);

                var psi = new ProcessStartInfo
                {
                    FileName = batchPath,
                    CreateNoWindow = true,
                    UseShellExecute = false,
                    WindowStyle = ProcessWindowStyle.Hidden
                };
                Process.Start(psi);
            }
            catch
            {
                // Self-deletion is optional, just close
            }
        }

        Application.Exit();
    }
}
