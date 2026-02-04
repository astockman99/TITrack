using System.Windows;

namespace TITrackOverlay;

public partial class App : Application
{
    public static string BaseUrl { get; private set; } = "http://127.0.0.1:8000";

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        // Parse command line arguments
        foreach (var arg in e.Args)
        {
            if (arg.StartsWith("--port="))
            {
                var port = arg.Substring("--port=".Length);
                BaseUrl = $"http://127.0.0.1:{port}";
            }
            else if (arg.StartsWith("--url="))
            {
                BaseUrl = arg.Substring("--url=".Length);
            }
        }
    }
}
