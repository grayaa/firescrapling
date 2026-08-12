import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { ScrollArea } from '../components/ui/scroll-area';
import { Globe, FileText, Download, Copy, ExternalLink, Hash, Braces, FileJson, Info } from 'lucide-react';
import { Badge } from '../components/ui/badge';
import { cn } from '../lib/utils';

export interface ScrapeResult {
  url: string;
  title: string;
  markdown: string;
  metadata?: any;
  data?: any; // Structured JSON data
}

interface ResultsViewProps {
  results: ScrapeResult[];
  activeJobType: 'scrape' | 'crawl';
}

export function ResultsView({ results, activeJobType }: ResultsViewProps) {
  const [selectedIdx, setSelectedIdx] = React.useState(0);
  const activeResult = results[selectedIdx];

  const handleCopy = () => {
    if (activeResult) {
      navigator.clipboard.writeText(activeResult.markdown);
    }
  };

  const handleCopyJson = () => {
    if (activeResult?.data) {
      navigator.clipboard.writeText(JSON.stringify(activeResult.data, null, 2));
    }
  };

  if (results.length === 0) return null;

  return (
    <div className="space-y-4 animate-in fade-in duration-500">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-heading font-semibold flex items-center gap-2">
          <FileText className="h-5 w-5 text-orange-500" />
          Extraction Results
          <Badge variant="secondary" className="ml-2 bg-orange-500/10 text-orange-500 border-orange-500/20">
            {results.length} {results.length === 1 ? 'Page' : 'Pages'}
          </Badge>
        </h3>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 min-h-[500px]">
        {/* List of pages for crawl results */}
        {activeJobType === 'crawl' && (
          <Card className="lg:col-span-1 bg-card/40 border-border overflow-hidden flex flex-col h-full max-h-[600px] backdrop-blur-md">
            <CardHeader className="p-3 border-b bg-muted/20">
              <CardTitle className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold">Crawled Pages</CardTitle>
            </CardHeader>
            <ScrollArea className="flex-1">
              <div className="p-2 space-y-1">
                {results.map((res, idx) => (
                  <button
                    key={idx}
                    onClick={() => setSelectedIdx(idx)}
                    className={cn(
                      "w-full text-left p-2 rounded-md transition-all text-xs border",
                      selectedIdx === idx 
                        ? "bg-orange-500/10 border-orange-500/30 text-orange-400 font-medium" 
                        : "border-transparent hover:bg-muted text-muted-foreground"
                    )}
                  >
                    <div className="truncate font-semibold">{res.title || 'No Title'}</div>
                    <div className="truncate opacity-70 text-[10px]">{res.url}</div>
                  </button>
                ))}
              </div>
            </ScrollArea>
          </Card>
        )}

        {/* Main Content View */}
        <Card className={cn(
          "bg-card/40 border-border overflow-hidden flex flex-col h-full max-h-[600px] backdrop-blur-md shadow-xl",
          activeJobType === 'crawl' ? "lg:col-span-3" : "lg:col-span-4"
        )}>
          {activeResult && (
            <>
              <CardHeader className="p-4 border-b bg-muted/10 space-y-2">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-1">
                    <CardTitle className="text-lg font-heading line-clamp-1">{activeResult.title}</CardTitle>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Globe className="h-3 w-3" />
                      <a href={activeResult.url} target="_blank" rel="noopener noreferrer" className="hover:text-orange-400 underline flex items-center gap-1 transition-colors">
                        {activeResult.url}
                        <ExternalLink className="h-2.5 w-2.5" />
                      </a>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={handleCopy} className="h-8 border-white/10 text-[10px] font-bold uppercase tracking-widest">
                      <Copy className="h-3 w-3 mr-2" />
                      Copy MD
                    </Button>
                    {activeResult.data && (
                      <Button variant="outline" size="sm" onClick={handleCopyJson} className="h-8 border-white/10 text-[10px] font-bold uppercase tracking-widest bg-orange-500/5 text-orange-400 border-orange-500/20">
                        <Braces className="h-3 w-3 mr-2" />
                        Copy JSON
                      </Button>
                    )}
                  </div>
                </div>
              </CardHeader>
              
              <Tabs defaultValue={activeResult.data ? "structured" : "preview"} className="flex-1 flex flex-col overflow-hidden">
                <div className="px-4 border-b bg-muted/5">
                  <TabsList className="bg-transparent h-10 gap-6">
                    {activeResult.data && (
                      <TabsTrigger value="structured" className="data-[state=active]:bg-transparent data-[state=active]:border-b-2 data-[state=active]:border-orange-500 data-[state=active]:shadow-none data-[state=active]:text-orange-400 rounded-none px-0 h-10 text-[10px] font-bold uppercase tracking-widest">
                        <FileJson className="h-3 w-3 mr-2" />
                        Structured Data
                      </TabsTrigger>
                    )}
                    <TabsTrigger value="preview" className="data-[state=active]:bg-transparent data-[state=active]:border-b-2 data-[state=active]:border-orange-500 data-[state=active]:shadow-none data-[state=active]:text-orange-400 rounded-none px-0 h-10 text-[10px] font-bold uppercase tracking-widest">
                      Markdown Preview
                    </TabsTrigger>
                    <TabsTrigger value="meta" className="data-[state=active]:bg-transparent data-[state=active]:border-b-2 data-[state=active]:border-orange-500 data-[state=active]:shadow-none data-[state=active]:text-orange-400 rounded-none px-0 h-10 text-[10px] font-bold uppercase tracking-widest">
                      Technical Info
                    </TabsTrigger>
                  </TabsList>
                </div>

                <div className="flex-1 overflow-hidden relative">
                  {activeResult.data && (
                    <TabsContent value="structured" className="h-full m-0 p-0 focus-visible:ring-0">
                      <ScrollArea className="h-full bg-black/40 p-4 font-mono text-xs">
                         <div className="bg-zinc-950/80 p-6 rounded-xl border border-white/5 shadow-inner">
                            <pre className="text-emerald-400/90 leading-relaxed whitespace-pre-wrap">
                              {JSON.stringify(activeResult.data, null, 2)}
                            </pre>
                         </div>
                      </ScrollArea>
                    </TabsContent>
                  )}

                  <TabsContent value="preview" className="h-full m-0 p-0 focus-visible:ring-0">
                    <ScrollArea className="h-full bg-zinc-950/40 p-6 font-mono text-sm leading-relaxed">
                      <div className="prose prose-invert prose-orange max-w-none">
                        <pre className="whitespace-pre-wrap bg-transparent p-0 text-orange-100/80 font-mono text-xs sm:text-sm">
                          {activeResult.markdown}
                        </pre>
                      </div>
                    </ScrollArea>
                  </TabsContent>
                  
                  <TabsContent value="meta" className="h-full m-0 p-0 focus-visible:ring-0">
                    <div className="p-8 space-y-6">
                      {activeResult.metadata ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                          {Object.entries(activeResult.metadata).map(([key, value]) => (
                             key !== 'structured_data' && (
                              <div key={key} className="space-y-1.5 group">
                                <div className="text-[9px] uppercase text-muted-foreground font-black tracking-tighter flex items-center gap-1.5">
                                  <Info className="h-2.5 w-2.5 text-orange-500/50" />
                                  {key.replace('_', ' ')}
                                </div>
                                <div className="text-xs font-mono bg-white/5 group-hover:bg-white/10 transition-colors p-3 rounded-lg border border-white/5 font-medium text-orange-100/70">
                                  {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                                </div>
                              </div>
                             )
                          ))}
                        </div>
                      ) : (
                        <div className="text-center py-12 text-muted-foreground">
                          No technical metadata available.
                        </div>
                      )}
                    </div>
                  </TabsContent>
                </div>
              </Tabs>
            </>
          )}
        </Card>
      </div>
    </div>
  );
}
