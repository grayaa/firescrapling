import React from 'react';
import { 
  Check, 
  ChevronDown, 
  HelpCircle, 
  Star, 
  Zap, 
  Shield, 
  Globe, 
  Terminal, 
  Activity,
  ArrowRight
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Switch } from '../components/ui/switch';
import { Label } from '../components/ui/label';
import { cn } from '../lib/utils';

export function SaaSInternalPricing() {
  const [isYearly, setIsYearly] = React.useState(false);

  const plans = [
    {
      name: "Free",
      price: 0,
      description: "BYOK orchestration — your Scrape.do/Scrapfly key pays for bytes.",
      features: [
        "Bring your own provider key",
        "Escalation ladder + domain profiles",
        "Estimated savings dashboard",
        "1k pages / month soft cap",
      ],
      cta: "Get Started",
      featured: false
    },
    {
      name: "Pro",
      price: isYearly ? 39 : 49,
      description: "Flat workspace plan for production crawls and higher concurrency.",
      features: [
        "Everything in Free",
        "Higher concurrency + pages/month",
        "Optional managed fetch (platform key)",
        "Webhooks + Redis queue",
        "Email support",
      ],
      cta: "Go Pro",
      featured: true
    },
    {
      name: "Team",
      price: isYearly ? 99 : 129,
      description: "Seats, managed mode, and room for media extractors / MCP.",
      features: [
        "Everything in Pro",
        "Team seats",
        "Managed fetch included",
        "Priority queue",
        "Media extract endpoints",
      ],
      cta: "Start Team",
      featured: false
    }
  ];

  const faqs = [
    {
      q: "Do you sell scrape credits?",
      a: "No. Core pricing is flat per workspace. You bring your own Scrape.do or Scrapfly key (BYOK); their meter pays for bytes."
    },
    {
      q: "What is managed fetch?",
      a: "On Pro/Team we can fall back to a platform provider key when you have not attached BYOK credentials. Free plans are BYOK-first."
    },
    {
      q: "How are savings calculated?",
      a: "Estimated units versus always using ASP/anti-bot. See docs/fetch-savings.md — labeled estimated in the dashboard."
    },
    {
      q: "Can I cancel anytime?",
      a: "Yes. Stripe subscriptions can be canceled from billing; BYOK keys remain under your control."
    }
  ];

  const [openFaq, setOpenFaq] = React.useState<number | null>(0);

  return (
    <section className="py-24 container mx-auto px-6 space-y-16 animate-in fade-in duration-1000">
      <div className="text-center space-y-6">
        <div className="space-y-2">
          <h2 className="text-4xl md:text-5xl font-heading font-black tracking-tight text-white uppercase">BYOK + flat plans</h2>
          <p className="text-muted-foreground text-sm uppercase tracking-widest font-bold">Your provider key pays for bytes — we sell orchestration</p>
        </div>
        
        <div className="flex items-center justify-center gap-4">
          <Label className={cn("text-xs font-bold uppercase transition-colors", !isYearly ? "text-white" : "text-muted-foreground")}>Monthly</Label>
          <Switch 
            checked={isYearly} 
            onCheckedChange={setIsYearly} 
            className="data-[state=checked]:bg-orange-600"
          />
          <div className="flex items-center gap-2">
            <Label className={cn("text-xs font-bold uppercase transition-colors", isYearly ? "text-white" : "text-muted-foreground")}>Yearly</Label>
            <Badge className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20 text-[10px] font-black uppercase tracking-widest">2 Months Free</Badge>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        {plans.map((p, i) => (
          <Card 
            key={i} 
            className={cn(
              "relative bg-[#0A0A0B]/60 backdrop-blur-xl border-white/5 shadow-2xl overflow-hidden group transition-all duration-300 hover:border-primary/30 active:scale-[0.99]",
              p.featured && "border-primary/50 ring-2 ring-primary/20 scale-105 z-10"
            )}
          >
            {p.featured && (
              <div className="absolute top-0 right-0 p-3">
                <Badge className="bg-primary text-primary-foreground font-black uppercase tracking-tighter text-[9px] px-2 py-0.5 shadow-xl shadow-primary/20">Most Popular</Badge>
              </div>
            )}
            
            <CardHeader className="p-8 space-y-4">
              <div className="space-y-1">
                <CardTitle className="text-xl font-heading font-black text-white uppercase">{p.name}</CardTitle>
                <CardDescription className="text-xs font-bold uppercase tracking-widest text-muted-foreground">{p.description}</CardDescription>
              </div>
              <div className="flex items-baseline gap-1">
                 <span className="text-4xl font-heading font-black text-white">
                   {typeof p.price === 'number' ? `$${p.price}` : p.price}
                 </span>
                 {typeof p.price === 'number' && <span className="text-xs font-bold uppercase text-muted-foreground tracking-widest">/mo</span>}
              </div>
            </CardHeader>

            <CardContent className="px-8 pb-8 space-y-6 border-t border-white/5 pt-8 bg-white/[0.01]">
               <ul className="space-y-4">
                 {p.features.map((f, j) => (
                   <li key={j} className="flex items-start gap-3 text-sm text-zinc-400 group-hover:text-zinc-200 transition-colors">
                     <Check className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                     <span>{f}</span>
                   </li>
                 ))}
               </ul>
            </CardContent>

            <CardFooter className="p-8 pt-0 bg-white/[0.01]">
               <Button className={cn(
                 "w-full h-12 font-black uppercase tracking-widest shadow-xl transition-all",
                 p.featured ? "bg-primary hover:bg-primary/90 shadow-primary/20" : "bg-white/5 border border-white/10 hover:bg-white/10"
               )}>
                 {p.cta} <ArrowRight className="ml-2 h-4 w-4" />
               </Button>
            </CardFooter>
          </Card>
        ))}
      </div>

      {/* FAQ Section */}
      <div className="max-w-3xl mx-auto space-y-12 pt-16">
        <div className="text-center space-y-2">
           <h3 className="text-2xl font-heading font-black text-white uppercase flex items-center justify-center gap-3">
             <HelpCircle className="h-6 w-6 text-primary" /> Common Questions
           </h3>
           <p className="text-muted-foreground text-xs uppercase tracking-widest font-bold">Everything you need to know about FireScrailing</p>
        </div>

        <div className="space-y-4">
          {faqs.map((f, i) => (
            <div 
              key={i} 
              className="group rounded-2xl border border-white/5 bg-white/[0.02] overflow-hidden transition-all hover:bg-white/[0.05]"
            >
               <button 
                 onClick={() => setOpenFaq(openFaq === i ? null : i)}
                 className="w-full p-6 text-left flex items-center justify-between"
               >
                 <span className="text-sm font-bold text-white uppercase tracking-widest">{f.q}</span>
                 <ChevronDown className={cn("h-4 w-4 text-muted-foreground transition-transform duration-300", openFaq === i && "rotate-180 text-primary")} />
               </button>
               <div className={cn(
                 "px-6 overflow-hidden transition-all duration-300 ease-in-out",
                 openFaq === i ? "max-h-40 pb-6 opacity-100" : "max-h-0 opacity-0"
               )}>
                  <p className="text-sm text-muted-foreground leading-relaxed">{f.a}</p>
               </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
