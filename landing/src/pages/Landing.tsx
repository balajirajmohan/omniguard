import { Nav } from '../components/Nav';
import { Footer } from '../components/Footer';
import { Hero } from '../sections/Hero';
import { Problem } from '../sections/Problem';
import { HowItWorks } from '../sections/HowItWorks';
import { DecisionLab } from '../sections/DecisionLab';
import { DigitalTwin } from '../sections/DigitalTwin';
import { Architecture } from '../sections/Architecture';
import { UseCases } from '../sections/UseCases';
import { Differentiation } from '../sections/Differentiation';
import { Adoption } from '../sections/Adoption';
import { FinalCTA } from '../sections/FinalCTA';

export default function Landing() {
  return (
    <>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[60] focus:rounded-md focus:bg-cyan focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-graphite"
      >
        Skip to content
      </a>
      <Nav />
      <main id="main">
        <Hero />
        <Problem />
        <HowItWorks />
        <DecisionLab />
        <DigitalTwin />
        <Architecture />
        <UseCases />
        <Differentiation />
        <Adoption />
        <FinalCTA />
      </main>
      <Footer />
    </>
  );
}
