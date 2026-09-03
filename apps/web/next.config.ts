import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Артефакт для деплоя SFR-4: standalone-сборка без node_modules хоста.
  output: "standalone",
  // Плавающий индикатор dev-инструментов пачкал скриншоты визуальной сверки.
  devIndicators: false,
};

export default nextConfig;
