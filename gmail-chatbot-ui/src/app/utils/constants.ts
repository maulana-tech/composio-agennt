export const API_URL = "http://localhost:8000";

export const suggestions = [
  { id: "1", title: "Search Web", description: "Search anything on the web", icon: "🔍", prompt: "Search for " },
  { id: "2", title: "Send Email", description: "Compose and send email", icon: "📧", prompt: "Send an email to " },
  { id: "3", title: "Extract Content", description: "Extract from any URL", icon: "📄", prompt: "Extract content from " },
  { id: "4", title: "Generate PDF", description: "Create PDF reports", icon: "📑", prompt: "Generate a PDF report about " },
];

export const getCardColor = (index: number) => {
  const colors = [
    "from-teal-500/20 to-teal-600/10 border-teal-500/30 hover:border-teal-400/50",
    "from-blue-500/20 to-blue-600/10 border-blue-500/30 hover:border-blue-400/50",
    "from-purple-500/20 to-purple-600/10 border-purple-500/30 hover:border-purple-400/50",
    "from-emerald-500/20 to-emerald-600/10 border-emerald-500/30 hover:border-emerald-400/50",
  ];
  return colors[index % colors.length];
};

export const getLogTypeColor = (type: string) => {
  switch (type) {
    case "search": return "text-blue-400 bg-blue-500/20 border-blue-500/30";
    case "extract": return "text-purple-400 bg-purple-500/20 border-purple-500/30";
    case "crawl": return "text-green-400 bg-green-500/20 border-green-500/30";
    case "map": return "text-orange-400 bg-orange-500/20 border-orange-500/30";
    case "email": return "text-cyan-400 bg-cyan-500/20 border-cyan-500/30";
    case "pdf": return "text-red-400 bg-red-500/20 border-red-500/30";
    default: return "text-gray-400 bg-gray-500/20 border-gray-500/30";
  }
};

export const formatDate = (dateStr: string) => {
  const date = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const mins = Math.floor(diff / (1000 * 60));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
};

export const needsAgentPanel = (text: string) => {
  const lowerText = text.toLowerCase();
  return (
    lowerText.includes("search") || lowerText.includes("cari") || lowerText.includes("find") ||
    lowerText.includes("extract") || lowerText.includes("ambil") ||
    lowerText.includes("crawl") ||
    lowerText.includes("map") || lowerText.includes("sitemap") ||
    lowerText.includes("email") || lowerText.includes("kirim") || lowerText.includes("draft") ||
    lowerText.includes("pdf") || lowerText.includes("report") || lowerText.includes("generate")
  );
};

export const detectLogType = (text: string): { type: string; title: string; detail: string } | null => {
  const lowerText = text.toLowerCase();
  
  if (lowerText.includes("search") || lowerText.includes("cari") || lowerText.includes("find")) {
    return { type: "search", title: "Tavily Search", detail: `Searching: "${text.slice(0, 50)}..."` };
  }
  if (lowerText.includes("extract") || lowerText.includes("ambil")) {
    return { type: "extract", title: "Tavily Extract", detail: "Extracting content from URL..." };
  }
  if (lowerText.includes("crawl")) {
    return { type: "crawl", title: "Tavily Crawl", detail: "Crawling website..." };
  }
  if (lowerText.includes("map") || lowerText.includes("sitemap")) {
    return { type: "map", title: "Tavily Map", detail: "Mapping website structure..." };
  }
  if (lowerText.includes("email") || lowerText.includes("kirim") || lowerText.includes("draft")) {
    return { type: "email", title: "Gmail Action", detail: "Processing email request..." };
  }
  if (lowerText.includes("pdf") || lowerText.includes("report") || lowerText.includes("generate")) {
    return { type: "pdf", title: "PDF Generator", detail: "Generating PDF report..." };
  }
  
  return null;
};
