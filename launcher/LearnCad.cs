using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Windows.Forms;

namespace LearnCad
{
    internal static class Program
    {
        [STAThread]
        private static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new SplashForm());
        }
    }

    internal sealed class SplashForm : Form
    {
        [DllImport("user32.dll")]
        private static extern bool SetForegroundWindow(IntPtr hWnd);

        [DllImport("user32.dll")]
        private static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

        private readonly Timer _timer;
        private readonly Label _status;
        private Process _child;
        private DateTime _started;
        private int _ticks;
        private bool _closing;

        public SplashForm()
        {
            Text = "LearnCad";
            FormBorderStyle = FormBorderStyle.None;
            StartPosition = FormStartPosition.CenterScreen;
            ClientSize = new Size(560, 320);
            BackColor = Color.FromArgb(8, 8, 8);
            TopMost = true;
            ShowInTaskbar = true;

            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }

            var logo = LoadLogo();
            if (logo != null)
            {
                var picture = new PictureBox
                {
                    Image = logo,
                    SizeMode = PictureBoxSizeMode.Zoom,
                    Bounds = new Rectangle(60, 58, 440, 123),
                    BackColor = Color.Transparent
                };
                Controls.Add(picture);
            }
            else
            {
                var title = new Label
                {
                    Text = "LearnCad",
                    ForeColor = Color.FromArgb(245, 245, 245),
                    Font = new Font("Segoe UI", 36, FontStyle.Bold),
                    AutoSize = true,
                    Location = new Point(60, 70)
                };
                Controls.Add(title);
            }

            var line = new Panel
            {
                Bounds = new Rectangle(60, 206, 440, 3),
                BackColor = Color.FromArgb(255, 122, 24)
            };
            Controls.Add(line);

            _status = new Label
            {
                Text = "Starting your workshop...",
                ForeColor = Color.FromArgb(200, 208, 218),
                Font = new Font("Segoe UI", 10, FontStyle.Regular),
                AutoSize = true,
                Location = new Point(60, 224)
            };
            Controls.Add(_status);

            var hint = new Label
            {
                Text = "Learn by building.",
                ForeColor = Color.FromArgb(155, 176, 198),
                Font = new Font("Segoe UI", 9, FontStyle.Regular),
                AutoSize = true,
                Location = new Point(60, 276)
            };
            Controls.Add(hint);

            _timer = new Timer { Interval = 500 };
            _timer.Tick += OnTick;
            Shown += OnShown;
        }

        private static Image LoadLogo()
        {
            try
            {
                var baseDir = AppDomain.CurrentDomain.BaseDirectory;
                var path = Path.Combine(baseDir, "assets", "logo-horizontal.png");
                if (!File.Exists(path))
                    path = Path.Combine(baseDir, "logo-horizontal.png");
                if (File.Exists(path))
                    return Image.FromFile(path);
            }
            catch { }
            return null;
        }

        private void OnShown(object sender, EventArgs e)
        {
            _started = DateTime.UtcNow;
            _timer.Start();
            try
            {
                var existing = FindExisting();
                if (existing != null)
                {
                    BringForward(existing);
                    CloseSplash();
                    return;
                }

                var engine = FindEngine();
                if (engine == null)
                {
                    _timer.Stop();
                    MessageBox.Show(
                        this,
                        "LearnCad could not find its modeling engine. Please reinstall LearnCad.",
                        "LearnCad",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Error);
                    CloseSplash();
                    return;
                }

                var info = new ProcessStartInfo
                {
                    FileName = engine,
                    WorkingDirectory = Path.GetDirectoryName(engine),
                    UseShellExecute = false,
                    CreateNoWindow = false
                };
                info.EnvironmentVariables["LEARNCAD"] = "1";
                _child = Process.Start(info);
            }
            catch (Exception)
            {
                _timer.Stop();
                MessageBox.Show(
                    this,
                    "LearnCad could not start. Please reinstall LearnCad.",
                    "LearnCad",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error);
                CloseSplash();
            }
        }

        private void OnTick(object sender, EventArgs e)
        {
            if (_closing)
                return;

            _ticks++;
            var dots = new string('.', _ticks % 4);
            _status.Text = "Starting your workshop" + dots;

            var elapsed = DateTime.UtcNow - _started;
            if (elapsed.TotalSeconds > 20)
                _status.Text = "First launch can take a minute" + dots;

            if (_child != null)
            {
                try
                {
                    if (_child.HasExited)
                    {
                        _timer.Stop();
                        MessageBox.Show(
                            this,
                            "LearnCad closed before the workspace opened. Please try again.",
                            "LearnCad",
                            MessageBoxButtons.OK,
                            MessageBoxIcon.Error);
                        CloseSplash();
                        return;
                    }

                    _child.Refresh();
                    var title = _child.MainWindowTitle ?? "";
                    if (title.IndexOf("LearnCad", StringComparison.OrdinalIgnoreCase) >= 0)
                    {
                        _timer.Stop();
                        BringForward(_child);
                        _status.Text = "Opening your workspace...";
                        var done = new Timer { Interval = 1200 };
                        done.Tick += (s, ev) =>
                        {
                            done.Stop();
                            done.Dispose();
                            CloseSplash();
                        };
                        done.Start();
                        return;
                    }

                    if (title.Length > 0 && elapsed.TotalSeconds > 45)
                    {
                        // A window exists even if branding is still catching up.
                        _timer.Stop();
                        _status.Text = "Opening your workspace...";
                        CloseSplash();
                        return;
                    }
                }
                catch { }
            }

            if (elapsed.TotalSeconds > 150)
            {
                _timer.Stop();
                CloseSplash();
            }
        }

        private static Process FindExisting()
        {
            foreach (var process in Process.GetProcessesByName("FreeCAD"))
            {
                try
                {
                    if (process.MainWindowHandle != IntPtr.Zero)
                        return process;
                }
                catch { }
            }
            return null;
        }

        private static void BringForward(Process process)
        {
            try
            {
                if (process.MainWindowHandle != IntPtr.Zero)
                {
                    ShowWindow(process.MainWindowHandle, 9);
                    SetForegroundWindow(process.MainWindowHandle);
                }
            }
            catch { }
        }

        private static string FindEngine()
        {
            var env = Environment.GetEnvironmentVariable("LEARNCAD_ENGINE");
            if (!string.IsNullOrEmpty(env) && File.Exists(env))
                return env;

            var roots = new[]
            {
                Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
                Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs")
            };

            foreach (var root in roots)
            {
                if (string.IsNullOrEmpty(root))
                    continue;
                foreach (var name in new[] { "FreeCAD 1.1", "FreeCAD 1.2", "FreeCAD 1.0", "FreeCAD" })
                {
                    var path = Path.Combine(root, name, "bin", "FreeCAD.exe");
                    if (File.Exists(path))
                        return path;
                }
            }

            // Portable installs: look for a FreeCAD* folder next to LearnCad.
            try
            {
                var baseDir = AppDomain.CurrentDomain.BaseDirectory;
                foreach (var dir in Directory.GetDirectories(baseDir, "FreeCAD*"))
                {
                    var path = Path.Combine(dir, "bin", "FreeCAD.exe");
                    if (File.Exists(path))
                        return path;
                }
                var local = Path.Combine(baseDir, "FreeCAD.exe");
                if (File.Exists(local))
                    return local;
            }
            catch { }

            return null;
        }

        private void CloseSplash()
        {
            if (_closing)
                return;
            _closing = true;
            _timer.Stop();
            Close();
            Application.Exit();
        }
    }
}
