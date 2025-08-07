import dotenv from 'dotenv';
import { logger } from './utils/logger';
import { NewsService } from './services/news';
import { ProfileService } from './services/profiles';

dotenv.config();

async function main() {
  try {
    logger.info('🚀 Starting True AI Builders...');
    
    // Initialize services
    const newsService = new NewsService();
    const profileService = new ProfileService();
    
    logger.info('✅ All services initialized');
    logger.info('📝 Ready to implement logic!');
    
  } catch (error) {
    logger.error('❌ Error starting application:', error);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}
