import { logger } from '../utils/logger';
import OpenAI from 'openai';

export class NewsService {
  private gnewsApiKey: string;
  private openai: OpenAI;

  constructor() {
    this.gnewsApiKey = process.env.GNEWS_API_KEY || '';
    this.openai = new OpenAI({
      apiKey: process.env.OPENAI_API_KEY,
    });

    if (!this.gnewsApiKey) {
      logger.warn('GNEWS_API_KEY not found in environment variables');
    } else {
      logger.info('News service initialized with GNews API key');
    }

    if (!this.openai) {
      logger.warn('OPENAI_API_KEY not found in environment variables');
    } else {
      logger.info('News service initialized with OPENAI API key');
    }
  }

  async scrapeNews(): Promise<Array<{ title: string; description: string; content: string }>> {
    logger.info('Scraping news from GNews...');

    try {
      const now = new Date().toISOString();
      const yesterday = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(); 

      const query = 'AI OR artificial intelligence';
      const url = `https://gnews.io/api/v4/search?q=${encodeURIComponent(query)}&apikey=${this.gnewsApiKey}&lang=en&max=10&from=${yesterday}&to=${now}`;
      console.log('API URL:', url);
      
      const response = await fetch(url);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json() as { articles?: Array<any> };
      logger.info(`📰 Found ${data.articles?.length || 0} articles from GNews`);
      
      // Map to only the fields we want
      const mappedArticles = data.articles?.map(article => ({
        title: article.title,
        description: article.description,
        content: (article.content || '').replace(/\s*\[\d+\s*chars\]$/, '')
      })) || [];
      return mappedArticles;
    } catch (error) {
      logger.error('Error fetching news:', error);
      return [];
    }
  } 

  async generateSummary(articles: Array<{ title: string; description: string; content: string }>): Promise<string> {
    const articlesText = articles.map((article, index) => 
      `[${index + 1}] ${article.title}\n${article.description}\n${article.content}`
    ).join('\n\n');

    const summarySystemPrompt = `
You write a tight, high-context morning blurb for technical AI founders, senior product and engineering leaders, and active investors in San Francisco’s builder ecosystem. Your audience is mostly earlier-stage, experimental builders — people shipping quickly, working with real-world constraints, and making constant trade-offs to get core features into the world.

Your input is AI news from the last 24 hours — choose only the most strategically or technically relevant developments for active builders today.

Purpose:
Surface immediately relevant insights that help scrappy builders think about where to focus, what to adapt, and which opportunities might open or close in the near term — without overstating significance or making assumptions beyond what is known.

Rules:
1. Selectivity: Select at most TWO stories. If more than two are relevant, choose the two with the clearest near-term implications for active builders and ignore the rest. If only one is materially relevant, cover just that one.
2. Depth over breadth: Instead of headline recaps, extract the core builder-facing insight:
   - Technical angle (e.g., model capabilities, infra choices, latency, architecture trade-offs)
   - Founder/market angle (e.g., GTM timing, platform risk, opportunity gaps from big player moves)
3. Accuracy over hype:
   - Do not frame something as a breakthrough unless the provided details support it.
   - If reception or coverage is mixed, acknowledge uncertainty or limitations.
   - Keep recommendations tentative when the practical impact is not yet proven.
4. Write from the perspective of someone who understands the reality of earlier-stage building:
   - Prioritizing speed to market and resource efficiency
   - Avoiding unnecessary complexity unless it’s a competitive lever
   - Watching for ways big industry moves create openings for new entrants
5. No fluff: Skip generic intros, industry truisms, or over-explaining common terms.
6. High-context voice: Write as if catching up with a peer in the trenches — confident but measured, showing why it might matter now.
7. Source integrity:
   - Use only the details in the input; no invented facts, numbers, features, or quotes.
   - If coverage is thin or the impact is unclear, say so rather than speculate.
8. Format:
   - 2–3 flowing paragraphs (220–300 words)
   - No lists, bullets, or links
   - Feels like part of an ongoing builder-to-builder conversation
    `;

    const summary = await this.openai.chat.completions.create({
      model: "gpt-4o",
      messages: [{ role: "system", content: summarySystemPrompt }, { role: "user", content: articlesText }],
      temperature: 0.4,
    });

    const summaryText = summary.choices[0]?.message?.content?.trim() || '';

    return summaryText;
  }

  async generateQuestions( summaryText: string ): Promise<string> {
    const questionsSystemPrompt = `
You are designing 2–4 short, high-signal discussion prompts for the SF AI builder community, based ONLY on the provided summary of the most relevant AI news from the last 24 hours.

Audience:
Scrappy, earlier-stage, experimental builders — technical founders, product leads, and investors who move fast, work with real-world constraints, and care about getting core features into users’ hands quickly. They might work on hardware, software, or AI infra, but they’re not large-scale incumbents with unlimited resources.

Purpose:
Turn the concrete developments in the summary into broad, high-leverage questions that make builders stop and think about their own roadmap, infra choices, and positioning. The goal is not to get them to comment only on the specific companies or products mentioned — but to use those as jumping-off points for ecosystem-level and builder-level reflection.

Transformation approach:
- Start with the specific news item.
- Zoom out to the underlying decision space, trade-off, or opportunity it represents.
- Frame the question so it applies to builders across different industries and product types.

Rules:
1. Use only the provided summary as your source. No new facts or companies.
2. You do not need to cover every topic in the summary. Choose the ones with the clearest generalizable implications.
3. Frame each question for personal reflection and experience-sharing; avoid assuming a specific outcome.
4. Center the angle on:
   - Opportunities or gaps created by big player moves
   - Capabilities that could shift roadmap timing or sequencing
   - Risks that require hedging or faster adaptation
   - Changes in ecosystem dynamics (supplier landscape, partnerships, talent flow)
   - Decisions about dependencies, control, and resource allocation
5. Make the link between the news and its relevance explicit — no vague “what do you think” prompts.
6. Tone:
   - Conversational, peer-to-peer — as if speaking with another founder over coffee
   - Curious, open-ended, and high-context
7. Format:
   - Exactly 2–4 questions
   - Each question is 1–2 sentences max
   - Avoid generic prompts, industry truisms, or yes/no framing

Example transformation for style only:
News: A major company shutters its custom AI chip program.
Zoomed-out question: When a big player backs away from vertical integration, how do you decide whether that’s your opening to move in — or a signal to steer clear?
    `;

    const questions = await this.openai.chat.completions.create({
      model: "gpt-4o",
      messages: [{ role: "system", content: questionsSystemPrompt }, { role: "user", content: summaryText }],
      temperature: 0.5,
    });
    const questionsText = questions.choices[0]?.message?.content?.trim() || '';

    return questionsText;
  }

  async sendEmailSummary(): Promise<void> {
    logger.info('Sending email summary...');
    // TODO: Implement email sending
  }
}
