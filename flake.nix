{
  description = "TITrack - Torchlight Infinite Local Loot Tracker";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    let
      nixosModule =
        {
          config,
          lib,
          pkgs,
          ...
        }:
        let
          cfg = config.services.titrack;
          python = pkgs.python312;
          defaultPkg = python.pkgs.buildPythonApplication {
            pname = "titrack";
            version = "0.5.7";
            src = self;
            format = "pyproject";
            nativeBuildInputs = [ python.pkgs.setuptools ];
            propagatedBuildInputs = with python.pkgs; [
              fastapi
              uvicorn
              httptools
              uvloop
              watchfiles
              websockets
              python-dotenv
              pyyaml
              pywebview
              supabase
            ];
            buildInputs = with pkgs; [
              webkitgtk_4_1
              glib-networking
            ];
            doCheck = false;
          };
        in
        {
          options.services.titrack = {
            enable = lib.mkEnableOption "TITrack Torchlight Infinite loot tracker";

            package = lib.mkOption {
              type = lib.types.package;
              default = defaultPkg;
              description = "The titrack package to use.";
            };

            port = lib.mkOption {
              type = lib.types.port;
              default = 8000;
              description = "Port for the TITrack web UI.";
            };
          };

          config = lib.mkIf cfg.enable {
            systemd.user.services.titrack = {
              description = "TITrack Torchlight Infinite Loot Tracker";
              wantedBy = [ "default.target" ];
              after = [ "network.target" ];
              serviceConfig = {
                ExecStart = "${cfg.package}/bin/titrack serve --no-window --port ${toString cfg.port}";
                StandardOutput = "journal";
                StandardError = "journal";
                SyslogIdentifier = "titrack";
                Restart = "on-failure";
                RestartSec = "5s";
              };
            };
          };
        };
    in
    {
      nixosModules.default = nixosModule;
      nixosModules.titrack = nixosModule;
    }
    // flake-utils.lib.eachDefaultSystem (
      system:
      let
        pyproject = fromTOML (builtins.readFile ./pyproject.toml);
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python312;

        titrack = python.pkgs.buildPythonApplication {
          pname = "titrack";
          version = pyproject.project.version;
          src = ./.;
          format = "pyproject";

          nativeBuildInputs = [ python.pkgs.setuptools ];

          propagatedBuildInputs = with python.pkgs; [
            fastapi
            uvicorn
            httptools
            uvloop
            watchfiles
            websockets
            python-dotenv
            pyyaml
            pywebview
            supabase
          ];

          buildInputs = with pkgs; [
            webkitgtk_4_1
            glib-networking
          ];

          doCheck = false;

          meta = with pkgs.lib; {
            description = "Local loot tracker for Torchlight Infinite";
            homepage = "https://github.com/astockman99/TITrack";
            license = licenses.mit;
            maintainers = with pkgs.lib.maintainers; [ cholli ];
            platforms = platforms.linux;
            mainProgram = "titrack";
          };
        };
      in
      {
        packages.default = titrack;

        apps.default = {
          type = "app";
          program = "${titrack}/bin/titrack";
        };

        devShells.default = pkgs.mkShell {
          packages = [
            (python.withPackages (
              ps: with ps; [
                fastapi
                uvicorn
                httptools
                uvloop
                watchfiles
                websockets
                python-dotenv
                pyyaml
                pywebview
                supabase
                pytest
                pytest-cov
                black
                ruff
              ]
            ))
          ];

          buildInputs = with pkgs; [
            webkitgtk_4_1
            glib-networking
          ];

          shellHook = ''
            export PYTHONPATH="${toString ./.}/src:$PYTHONPATH"
            echo "TITrack dev shell ready. Run: python -m titrack serve --no-window"
          '';
        };
      }
    );
}
