"use client"

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BorderTrail } from "@/components/ui/border-trail";

export function Navigation() {
  const pathname = usePathname();

  const navItems = [
    { href: "/", label: "Propositions", icon: "🧠" },
    { href: "/memory", label: "Memory", icon: "💭" },
  ];

  return (
    <nav className="mb-8">
      <div className="flex space-x-4">
        {navItems.map((item) => {
          const isActive = 
            (pathname === "/" && item.href === "/") || 
            (pathname === item.href && item.href !== "/");

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`
                relative px-6 py-3 rounded-xl transition-all duration-300
                ${
                  isActive
                    ? "bg-white/20 text-white backdrop-blur-sm"
                    : "bg-white/5 text-gray-300 hover:bg-white/10 hover:text-white"
                }
              `}
            >
              {isActive && <BorderTrail size={40} />}
              <span className="relative z-10 flex items-center gap-2 font-medium">
                <span className="text-lg">{item.icon}</span>
                {item.label}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
