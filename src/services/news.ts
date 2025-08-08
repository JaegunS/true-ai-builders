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
      const yesterday = new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString();
      const query = 'AI OR artificial intelligence';

      const url = `https://gnews.io/api/v4/search?q=${encodeURIComponent(query)}&apikey=${this.gnewsApiKey}&lang=en&max=10&from=${yesterday}`;
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

  async generateSummary(articles: Array<{ title: string; description: string; content: string }>): Promise<{ articlesText: string, summaryText: string }> {
    const articlesText = articles.map((article, index) => 
      `[${index + 1}] ${article.title}\n${article.description}\n${article.content}`
    ).join('\n\n');

    const summarySystemPrompt = `
      You write a podcast-style morning blurb for SF AI builders and founders.

      Audience: Experienced AI founders, senior product and engineering leaders, active investors, and community builders. They already understand baseline startup and AI concepts — skip the “101” and avoid restating obvious industry truisms (e.g., “AI is growing fast” or “niche AI startups are attracting investment”).

      Input: 10 AI articles, each with title, description, and content (snippets). Some content may be truncated.

      Rules:
      - Use ONLY info present in the input. Do NOT invent names, numbers, dates, quotes, benchmarks, or features that do not appear.
      - It’s OK to use soft qualifiers like “coverage describes” or “reports say” where the article wording is vague.
      - Briefly identify lesser-known companies or products in one clause (e.g., “n8n, an open-source workflow automation tool”).
      - Tone: conversational, energetic, and informed — as if two seasoned founders were catching up over coffee, not reading the news aloud.
      - Assume the reader is deeply in the arena. Skip over-explaining terms, obvious strategy tropes, or “startup basics.” Avoid generic hypotheticals.
      - For each major story, include at least one non-obvious, high-leverage insight — but only if it can be directly inferred from the facts provided. 
      - If the article does not provide enough detail to support a non-obvious insight, explicitly note the limitation instead of speculating (e.g., “The coverage doesn’t specify technical details, making it unclear how this compares to prior benchmarks.”).
      - Never invent facts, numbers, names, features, timelines, or quotes that do not appear in the provided articles.
      - Avoid negative knowledge claims like “there are no details,” “coverage doesn’t dive into specifics,” or “unknown.” Prefer omission or the narrow attribution above.
      - Weave in at least one technical implication (e.g., iteration speed, inference efficiency, multimodal capabilities) AND one founder-facing implication (e.g., GTM timing, competitive positioning, platform dependency) for the day’s big stories.
      - Prioritize what’s strategically or technically important over headline repetition; add brief connective tissue to explain why it matters in context.
      - Merge related stories naturally (e.g., multiple GPT-5 articles), but surface distinct angles when they add value.
      - No bullets, no lists, no links, no JSON — just 2–4 flowing paragraphs (220–350 words) that feel like part of an ongoing, high-context conversation.
    `;

    const summary = await this.openai.chat.completions.create({
      model: "gpt-4o",
      messages: [{ role: "system", content: summarySystemPrompt }, { role: "user", content: articlesText }],
      temperature: 0.4,
    });

    const summaryText = summary.choices[0]?.message?.content?.trim() || '';

    return { articlesText, summaryText };
  }

  async generateQuestions(summary: { articlesText: string, summaryText: string }): Promise<string> {
    const questionsSystemPrompt = `
    You are a discussion architect for a community of highly engaged AI builders in San Francisco.

    Audience: Experienced AI founders, senior product and engineering leaders, active investors, and community builders. They already understand baseline startup and AI concepts — skip the “101” and avoid obvious or cliché prompts.

    Your goal: From a provided AI news summary and original article snippets, craft EXACTLY 2–4 short, compelling, conversation-driven questions that this audience will want to answer from their own lived experience and mission.

    Tone & Style:
    - Match the energy and voice of the morning summary — grounded, lightly energetic, and conversational.
    - Speak as if to peers over coffee, not in a formal panel.
    - Every question should feel worth the time of someone already building or investing at a high level.

    Rules:
    1. Ground all questions in the provided facts — no inventing names, numbers, features, or events.
    2. Use the news as a launchpad, but quickly connect it to the reader’s own work, challenges, or product strategy.
    3. Avoid “101” framing and irrelevant hypotheticals (e.g., “If you were Apple’s CEO…”). Keep the focus on what’s actionable or reflective for *them*.
    4. Touch on a mix of themes when relevant — technical implications, founder strategy, market positioning, team culture, ethics, the global AI race — but don’t force quotas.
    5. Avoid generic phrasing like “What are your thoughts?” — each question should be self-contained and spark a thoughtful, multi-dimensional response.
    `

    const questionsUserPrompt = `
    Original articles: ${summary.articlesText}
    Summary: ${summary.summaryText}
    `;

    const questions = await this.openai.chat.completions.create({
      model: "gpt-4o",
      messages: [{ role: "system", content: questionsSystemPrompt }, { role: "user", content: questionsUserPrompt }],
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
