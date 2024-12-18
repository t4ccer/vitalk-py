{
  description = "A very basic flake";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
    flake-parts = {
      url = "github:hercules-ci/flake-parts";
      inputs.nixpkgs-lib.follows = "nixpkgs";
    };
    git-hooks-nix = {
      url = "github:cachix/git-hooks.nix";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.nixpkgs-stable.follows = "nixpkgs";
    };
  };

  outputs =
    inputs@{ self, flake-parts, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      imports = [
        inputs.git-hooks-nix.flakeModule
      ];
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      perSystem =
        {
          config,
          self',
          inputs',
          pkgs,
          ...
        }:
        {
          packages.hello = pkgs.hello;
          pre-commit.settings.hooks = {
            nixfmt-rfc-style.enable = true;
            black.enable = true;
          };
          devShells.default = pkgs.mkShell {
            shellHook = config.pre-commit.installationScript;
            nativeBuildInputs = [
              (pkgs.python3.withPackages (
                ps: with ps; [
                  flask
                  pyserial
                  gunicorn
                ]
              ))
            ];
          };
        };
    };
}
