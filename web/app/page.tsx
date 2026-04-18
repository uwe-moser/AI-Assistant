import { Nav } from "@/components/Nav";
import { Hero } from "@/components/Hero";
import { Marquee } from "@/components/Marquee";
import { Architecture } from "@/components/Architecture";
import { Features } from "@/components/Features";
import { Demo } from "@/components/Demo";
import { Numbers } from "@/components/Numbers";
import { Author } from "@/components/Author";
import { Footer } from "@/components/Footer";
import { RevealManager } from "@/components/RevealManager";

export default function HomePage() {
  return (
    <>
      <Nav />
      <Hero />
      <Marquee />
      <Architecture />
      <Features />
      <Demo />
      <Numbers />
      <Author />
      <Footer />
      <RevealManager />
    </>
  );
}
