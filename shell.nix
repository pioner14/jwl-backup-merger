{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs.python312Packages; [
    python
    tkinter
    pytest
    tqdm
    pyinstaller
  ];

  shellHook = ''
    echo "JW Library Backup Merger development environment"
    echo "Python: $(python --version)"
    echo ""
    echo "Commands:"
    echo "  python jwl_backup_merger.py <input_dir>  - CLI версия"
    echo "  python jwl_backup_merger_gui.py          - GUI версия"
    echo "  pytest tests/ -v                         - Запуск тестов"
  '';
}
