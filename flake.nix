{
  description = "TITrack — Torchlight Infinite local loot tracker";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  };

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f system);
      version = (builtins.fromTOML (builtins.readFile ./pyproject.toml)).project.version;

      mkPython =
        pkgs: base:
        base.override {
          packageOverrides = _self: super: {
            pyiceberg = super.pyiceberg.overridePythonAttrs (_: {
              pythonRelaxDeps = [ "rich" "cachetools" ];
              doCheck = false;
            });
          };
        };
    in
    {
      packages = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          python = mkPython pkgs pkgs.python313;

          titrack = python.pkgs.buildPythonApplication {
            pname = "titrack";
            inherit version;
            pyproject = true;

            src = ./.;

            build-system = [ python.pkgs.setuptools ];

            # pywebview provides the native window, which is Windows-only
            # (EdgeChromium). On Linux/macOS TITrack runs in browser mode
            # (`titrack serve --no-window`), so the dependency is dropped
            # rather than pulling in the whole GTK/WebKit stack.
            pythonRemoveDeps = [ "pywebview" ];

            propagatedBuildInputs =
              with python.pkgs;
              [
                fastapi
                uvicorn
                supabase
              ]
              ++ (python.pkgs.uvicorn.optional-dependencies.standard or [ ]);

            # The item seed lives at the repo root (outside the package);
            # install it beside the package where get_resource_path() falls
            # back to for installed builds.
            postInstall = ''
              cp ${./tlidb_items_seed_en.json} \
                $out/${python.sitePackages}/titrack/tlidb_items_seed_en.json
            '';

            nativeCheckInputs = with python.pkgs; [
              pytestCheckHook
              httpx
            ];
            # Tests create databases under the user data dir fallback; give
            # them a writable HOME inside the sandbox.
            preCheck = ''
              export HOME=$TMPDIR
            '';

            meta = with pkgs.lib; {
              description = "Torchlight Infinite local loot tracker (browser mode on Linux: titrack serve --no-window)";
              homepage = "https://github.com/astockman99/TITrack";
              license = licenses.mit;
              mainProgram = "titrack";
              platforms = platforms.unix;
            };
          };
        in
        {
          default = titrack;
          titrack = titrack;
        }
      );

      apps = forAllSystems (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/titrack";
        };
      });

      devShells = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          python = mkPython pkgs pkgs.python314;
        in
        {
          default = pkgs.mkShell {
            packages = [
              (python.withPackages (
                ps: with ps; [
                  fastapi
                  uvicorn
                  supabase
                  pytest
                  pytest-cov
                  black
                  ruff
                ]
              ))
            ];
            shellHook = ''
              echo "TITrack dev shell — run: python -m titrack serve --no-window"
            '';
          };
        }
      );
    };
}
