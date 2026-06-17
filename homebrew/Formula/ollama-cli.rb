class OllamaCli < Formula
  desc "Ollama blob + manifest inspector with orphan detection"
  homepage "https://github.com/r14r/ollama-cli"
  url "https://github.com/r14r/ollama-cli/archive/refs/tags/v1.0.0.tar.gz"
  sha256 "90f999cfd06a5ff8b7a4b40933316ae37a7fd1ea8e8d45e87f731ad56e2819aa"
  license "MIT"

  depends_on "python@3.11"

  def install
    bin.install "ollama-cli.py" => "ollama-cli"
  end

  test do
    output = shell_output("#{bin}/ollama-cli --help")
    assert_match "Inspect Ollama blobs", output
  end
end
