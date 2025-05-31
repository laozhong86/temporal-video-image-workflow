#!/usr/bin/env node

/**
 * 项目部署工具
 * 
 * 此脚本用于将当前项目的所有文件复制并覆盖到指定的目标文件夹中
 * 使用方法: node deploy.js [目标路径]
 */

const fs = require('fs-extra');
const path = require('path');
const readline = require('readline');

// 如果未安装依赖项，尝试使用内置模块实现类似功能
let minimatch;
try {
  minimatch = require('minimatch');
} catch (err) {
  // 模块未安装，提供简单的后备方案
  minimatch = {
    minimatch: (path, pattern) => {
      const regExpEscape = (s) => s.replace(/[-/\^$*+?.()|[\]{}]/g, '\\$&');
      const fnmatch = pattern
        .replace(/\*\*/g, '__GLOBSTAR__')
        .replace(/\*/g, '[^/]*')
        .replace(/__GLOBSTAR__/g, '.*')
        .replace(/\?/g, '[^/]');
      const re = new RegExp(`^${regExpEscape(fnmatch)}$`);
      return re.test(path);
    }
  };
}

// 创建readline接口用于用户交互
const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

// 获取当前脚本所在的源目录
const sourceDir = path.resolve(__dirname, '..');

// 默认排除的文件和目录（不会被复制）
const defaultExcludes = [
  '.git',
  'node_modules',
  '.DS_Store',
  '.env.local',
  '.env.development.local',
  '.env.test.local',
  '.env.production.local'
];

// 从.deployignore文件加载排除规则
function loadIgnorePatterns(sourceDir) {
  const ignoreFilePath = path.join(sourceDir, '.deployignore');
  let patterns = [...defaultExcludes];
  
  if (fs.existsSync(ignoreFilePath)) {
    try {
      const content = fs.readFileSync(ignoreFilePath, 'utf8');
      const lines = content.split('\n').filter(line => {
        // 过滤空行和注释
        const trimmed = line.trim();
        return trimmed && !trimmed.startsWith('#');
      });
      
      patterns = [...patterns, ...lines];
      console.log(`已加载 ${lines.length} 条排除规则从 .deployignore`);
    } catch (err) {
      console.warn(`无法读取 .deployignore 文件: ${err.message}`);
      console.warn('将使用默认排除规则');
    }
  } else {
    console.log('未找到 .deployignore 文件，使用默认排除规则');
  }
  
  return patterns;
}

// 检查文件或目录是否应该被排除
function shouldExclude(filePath, patterns, baseDir) {
  // 获取相对路径以进行匹配
  const relativePath = path.relative(baseDir, filePath);
  
  // 检查是否匹配任何模式
  for (const pattern of patterns) {
    if (minimatch.minimatch(relativePath, pattern) || 
        minimatch.minimatch(path.basename(filePath), pattern)) {
      return true;
    }
  }
  
  return false;
}

/**
 * 主函数
 */
async function main() {
  // 检查依赖
  checkDependencies();
  // 检查命令行参数
  const args = process.argv.slice(2);
  if (args.length !== 1) {
    console.error('错误: 请提供目标目录路径');
    console.error('使用方法: node deploy.js [目标路径]');
    process.exit(1);
  }

  // 获取并解析目标目录路径
  let targetDir = args[0];
  targetDir = path.resolve(targetDir);

  // 检查目标路径是否存在，如果不存在则询问是否创建
  if (!fs.existsSync(targetDir)) {
    const answer = await askQuestion(`目标目录 "${targetDir}" 不存在，是否创建? (y/n): `);
    if (answer.toLowerCase() === 'y') {
      try {
        fs.mkdirSync(targetDir, { recursive: true });
        console.log(`已创建目录: ${targetDir}`);
      } catch (err) {
        console.error(`无法创建目录: ${err.message}`);
        process.exit(1);
      }
    } else {
      console.log('操作已取消');
      process.exit(0);
    }
  }

  // 检查目标是否为目录
  try {
    const stats = fs.statSync(targetDir);
    if (!stats.isDirectory()) {
      console.error(`错误: "${targetDir}" 不是一个目录`);
      process.exit(1);
    }
  } catch (err) {
    console.error(`无法访问目标路径: ${err.message}`);
    process.exit(1);
  }

  // 确认操作
  console.log(`源目录: ${sourceDir}`);
  console.log(`目标目录: ${targetDir}`);
  console.log('将要复制的文件将覆盖目标目录中的同名文件。');
  
  const confirmation = await askQuestion('确定要继续吗? (y/n): ');
  if (confirmation.toLowerCase() !== 'y') {
    console.log('操作已取消');
    process.exit(0);
  }

  // 加载排除规则
  const ignorePatterns = loadIgnorePatterns(sourceDir);
  console.log(`总共有 ${ignorePatterns.length} 条排除规则`);
  
  // 执行复制
  try {
    await copyDirectory(sourceDir, targetDir, ignorePatterns);
    console.log('\n✅ 部署完成!');
  } catch (err) {
    console.error(`❌ 部署失败: ${err.message}`);
    process.exit(1);
  } finally {
    rl.close();
  }
}

/**
 * 复制目录内容到目标目录
 * @param {string} source 源目录
 * @param {string} target 目标目录
 * @param {string[]} ignorePatterns 排除模式列表
 */
async function copyDirectory(source, target, ignorePatterns) {
  // 获取源目录中的所有文件和目录
  const entries = fs.readdirSync(source, { withFileTypes: true });
  
  let copyCount = 0;
  let skipCount = 0;

  for (const entry of entries) {
    const sourcePath = path.join(source, entry.name);
    const targetPath = path.join(target, entry.name);
    
    // 检查是否应该排除此文件或目录
    if (shouldExclude(sourcePath, ignorePatterns, sourceDir)) {
      console.log(`跳过: ${path.relative(sourceDir, sourcePath)}`);
      skipCount++;
      continue;
    }
    
    if (entry.isDirectory()) {
      // 确保目标目录存在
      fs.ensureDirSync(targetPath);
      
      // 递归复制子目录
      const { copied, skipped } = await copyDirectory(sourcePath, targetPath, ignorePatterns);
      copyCount += copied;
      skipCount += skipped;
    } else {
      // 复制文件
      try {
        fs.copyFileSync(sourcePath, targetPath);
        console.log(`复制: ${path.relative(sourceDir, sourcePath)}`);
        copyCount++;
      } catch (err) {
        console.error(`无法复制 ${sourcePath}: ${err.message}`);
        throw err;
      }
    }
  }
  
  return { copied: copyCount, skipped: skipCount };
}

/**
 * 提示用户并获取输入
 * @param {string} question 提示文本
 * @returns {Promise<string>} 用户输入
 */
function askQuestion(question) {
  return new Promise((resolve) => {
    rl.question(question, (answer) => {
      resolve(answer);
    });
  });
}

// 检查依赖
function checkDependencies() {
  try {
    // 检查是否需要安装依赖
    if (typeof minimatch.minimatch !== 'function') {
      console.warn('警告: minimatch 依赖未正确加载，将使用内置简化版本');
    }
  } catch (err) {
    console.warn('警告: 依赖检查失败', err.message);
  }
}

// 运行主函数
main().catch(err => {
  console.error(err);
  process.exit(1);
});
