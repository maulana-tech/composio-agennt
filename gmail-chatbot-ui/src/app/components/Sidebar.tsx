"use client";

import { HomeIcon, HistoryIcon, MailIcon, LayersIcon } from "./icons";

interface SidebarProps {
  showHistory: boolean;
  onHomeClick: () => void;
  onHistoryClick: () => void;
}

export default function Sidebar({ showHistory, onHomeClick, onHistoryClick }: SidebarProps) {
  return (
    <aside className="w-16 bg-[#0d1321] border-r border-gray-800/50 flex flex-col items-center py-4 gap-1">
      <div className="w-10 h-10 bg-gradient-to-br from-teal-400 to-cyan-500 rounded-lg flex items-center justify-center mb-6 text-white">
        <LayersIcon />
      </div>
      <nav className="flex flex-col gap-2">
        <button
          onClick={onHomeClick}
          className={`w-10 h-10 rounded-lg flex items-center justify-center transition-colors ${
            !showHistory ? "bg-gray-800/50 text-teal-400" : "text-gray-500 hover:bg-gray-800/50 hover:text-gray-300"
          }`}
        >
          <HomeIcon />
        </button>
        <button
          onClick={onHistoryClick}
          className={`w-10 h-10 rounded-lg flex items-center justify-center transition-colors ${
            showHistory ? "bg-gray-800/50 text-teal-400" : "text-gray-500 hover:bg-gray-800/50 hover:text-gray-300"
          }`}
        >
          <HistoryIcon />
        </button>
        <button className="w-10 h-10 rounded-lg text-gray-500 flex items-center justify-center hover:bg-gray-800/50 hover:text-gray-300 transition-colors">
          <MailIcon />
        </button>
      </nav>
    </aside>
  );
}
