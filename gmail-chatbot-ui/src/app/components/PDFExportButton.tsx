"use client";
import { useRef } from "react";
import jsPDF from "jspdf";
import { marked } from "marked";

interface PDFExportButtonProps {
  markdown: string;
  filename?: string;
}

export default function PDFExportButton({ markdown, filename = "report.pdf" }: PDFExportButtonProps) {
  const handleExport = async () => {
    const doc = new jsPDF({ unit: "pt", format: "a4" });
    // Convert markdown to HTML
    const html = await marked.parse(markdown);
    // Add HTML to PDF
    doc.html(html as string, {
      x: 40,
      y: 40,
      width: 520,
      windowWidth: 800,
      callback: function (doc) {
        doc.save(filename);
      },
    });
  };

  return (
    <button
      onClick={handleExport}
      className="mt-2 px-4 py-2 bg-teal-600 text-white rounded hover:bg-teal-700 transition"
    >
      Download as PDF
    </button>
  );
}
