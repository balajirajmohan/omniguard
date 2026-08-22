import { Reveal } from '../components/ui/Reveal';
import { ArrowRight, ButtonLink } from '../components/ui/Button';
import { DEMO_ROUTE } from '../config/endpoints';

export function FinalCTA() {
  return (
    <section className="relative overflow-hidden border-t border-hairline/70 py-24 sm:py-28 lg:py-32">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0">
        <div className="bg-grid mask-fade-edges absolute inset-0 opacity-60" />
        <div
          className="absolute bottom-[-30%] left-1/2 h-[520px] w-[980px] -translate-x-1/2 opacity-50"
          style={{
            background:
              'radial-gradient(ellipse at center, rgba(34,211,238,0.16), rgba(34,211,238,0) 68%)',
          }}
        />
      </div>

      <div className="relative mx-auto w-full max-w-[1200px] px-5 text-center sm:px-8">
        <Reveal>
          <h2 className="text-balance mx-auto max-w-3xl text-3xl font-semibold leading-[1.12] tracking-[-0.025em] text-ink sm:text-4xl lg:text-[2.9rem]">
            Do not wait for a cyber incident to become a physical one.
          </h2>
        </Reveal>
        <Reveal delay={0.1}>
          <p className="mx-auto mt-6 max-w-2xl text-[15px] leading-relaxed text-ink-dim sm:text-[17px]">
            See how OmniGuard intercepts an unsafe robot command, explains the decision, and
            contains the compromised identity in a live warehouse digital twin.
          </p>
        </Reveal>
        <Reveal delay={0.18}>
          <div className="mt-9 flex flex-wrap justify-center gap-3">
            <ButtonLink href={DEMO_ROUTE} size="lg">
              Start the Live Demo
              <ArrowRight />
            </ButtonLink>
            <ButtonLink href="#decision-lab" variant="secondary" size="lg">
              Review the Decision Flow
            </ButtonLink>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
