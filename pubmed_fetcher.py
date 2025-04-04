import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime
import tkinter as tk
from tkinter import ttk
import threading
import time

def read_references_from_file(file_path):
    references = []
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
        entries = content.split('\n\n')
        for entry in entries:
            entry = entry.strip()
            references.append(entry)
    return references

def download_pdf(pdf_url, save_path):
    try:
        # 添加请求头模拟浏览器访问
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive',
            'Referer': 'https://www.ncbi.nlm.nih.gov/pmc/'
        }

        # 设置超时时间
        pdf_response = requests.get(pdf_url, headers=headers, stream=True, timeout=30)

        if pdf_response.status_code == 200:
            # 确保目录存在
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            with open(save_path, 'wb') as file:
                for chunk in pdf_response.iter_content(chunk_size=8192):
                    if chunk:  # 过滤掉keep-alive新块
                        file.write(chunk)
            print(f"PDF文件已成功下载并保存到: {save_path}")
            return True
        else:
            print(f"下载PDF文件失败，状态码: {pdf_response.status_code}")
    except Exception as e:
        print(f"下载PDF文件时发生错误: {e}")
        return False


def search_pubmed(term):
    base_url = "https://pubmed.ncbi.nlm.nih.gov/"
    search_url = f"{base_url}?term={term}"
    response = requests.get(search_url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        article_links = soup.find_all('a', class_='docsum-title', href=True)
        # 根据这个警告信息特征来判断是否精准搜索到对应论文，如果是，只返回1篇链接
        if soup.find('div', class_='usa-alert usa-alert-slim usa-alert-info'):
            if article_links:
                return [base_url + article_links[0]['href']]
            else:
                return []
        elif soup.find('span', class_='single-result-redirect-message'):
            return [search_url]

        links = [base_url + link['href'] for link in article_links[:5]]
        return links
    else:
        print(f"进入PubMed搜索结果页面失败，状态码: {response.status_code}")
        return []

def fetch_paper_details(link):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
    article_response = requests.get(link, headers=headers)
    if article_response.status_code == 200:
        article_soup = BeautifulSoup(article_response.content, 'html.parser')
        # 查找摘要部分
        abstract_section = article_soup.find('div', {'class': 'abstract-content selected'})
        abstract_text = abstract_section.get_text(strip=True) if abstract_section else None

        # 查找标题部分
        title_section = article_soup.find('h1', {'class': 'heading-title'})
        title_text = title_section.get_text(strip=True) if title_section else None

        # 查找全文链接部分
        full_text_link_section = article_soup.find('a', class_='link-item pmc', href=True)
        full_text_link = full_text_link_section['href'] if full_text_link_section else None

        # 查找PDF链接
        pdf_link = None
        if full_text_link:
            try:
                text_link_response = requests.get(full_text_link, headers=headers, timeout=30)
                if text_link_response.status_code == 200:
                    text_link_soup = BeautifulSoup(text_link_response.content, 'html.parser')
                    pdf_meta_tag = text_link_soup.find('meta', attrs={'name': 'citation_pdf_url'})
                    pdf_link = pdf_meta_tag['content'] if pdf_meta_tag else None
                    if pdf_link:
                        # 创建保存PDF文件的路径
                        if title_text:
                            # 替换文件名中的非法字符
                            safe_title = "".join(
                                [c if c.isalnum() or c in [' ', '_', '-'] else '_' for c in title_text])
                            safe_title = safe_title.replace(' ', '_')[:100]  # 限制文件名长度
                            papers_dir = os.path.join(os.getcwd(), "full_text")
                            # 确保目录存在
                            os.makedirs(papers_dir, exist_ok=True)
                            pdf_save_path = os.path.join(papers_dir, f"{safe_title}.pdf")
                            # 下载PDF文件
                            download_success = download_pdf(pdf_link, pdf_save_path)
                            if not download_success:
                                print(f"PDF下载失败: {pdf_link}")
            except Exception as e:
                print(f"获取PDF链接时出错: {e}")
        return title_text, abstract_text, full_text_link
    else:
        print(f"访问论文失败，状态码: {article_response.status_code}")
        return None, None, None


def main(progress_var, root):
    # 定义文件路径为当前目录
    file_path = os.path.join(os.getcwd(), "references.txt")

    # 读取引用信息
    references = read_references_from_file(file_path)
    print(f"读取到 {len(references)} 篇论文的引用信息")

    # 存储摘要的列表
    abstracts = []

    # 存储标题的列表
    titles = []

    # 存储论文链接的列表
    all_links = []

    # 存储全文链接的列表
    full_text_links = []

    # 先计算每个引用的链接数量，以便精确计算进度
    total_tasks = 0
    link_counts = []

    for reference in references:
        links = search_pubmed(reference)
        link_count = len(links) if links else 0
        link_counts.append(link_count)
        total_tasks += link_count if link_count > 0 else 1  # 至少计算一个任务，即使没有找到链接

    completed_tasks = 0

    # 遍历每篇论文的引用信息并搜索PubMed
    for i, reference in enumerate(references, start=1):
        print(f"\n搜索论文 {i}: {reference}")
        links = search_pubmed(reference)
        all_links.extend(links)

        if links:
            print(f"找到 {len(links)} 篇相关论文")
            for j, link in enumerate(links, start=1):
                print(f"\n访问论文 {j} ({i}.{j}): {link}")
                title, abstract, full_text_link = fetch_paper_details(link)
                if title:
                    titles.append(title)
                    print(f"标题 {i}.{j}:\n{title}\n")
                else:
                    titles.append(None)
                    print(f"论文 {i}.{j} 没有找到标题内容")

                if abstract:
                    abstracts.append(abstract)
                    print(f"摘要 {i}.{j}:\n{abstract}\n")
                else:
                    abstracts.append(None)
                    print(f"论文 {i}.{j} 没有找到摘要内容")

                if full_text_link:
                    full_text_links.append(full_text_link)
                    print(f"全文链接 {i}.{j}:\n{full_text_link}\n")
                else:
                    full_text_links.append(None)
                    print(f"论文 {i}.{j} 没有找到全文链接")

                completed_tasks += 1
                progress_var.set((completed_tasks / total_tasks) * 100)
                root.update_idletasks()
                time.sleep(0.1)  # 模拟处理时间
        else:
            print(f"没有找到与引用信息 '{reference}' 相关的论文")
            titles.append(None)
            abstracts.append(None)
            full_text_links.append(None)
            completed_tasks += 1  # 仍然计算一个任务
            progress_var.set((completed_tasks / total_tasks) * 100)
            root.update_idletasks()
            time.sleep(0.1)  # 模拟处理时间

    # 获取当前时间作为文件名
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(os.getcwd(), "log")
    file_name = f"log_{current_time}.txt"
    full_file_path = os.path.join(file_path, file_name)

    # 确保文件夹存在
    os.makedirs(file_path, exist_ok=True)

    # 将摘要和标题内容写入文件
    with open(full_file_path, 'w', encoding='utf-8') as file:
        index = 0
        for i, reference in enumerate(references, start=1):
            file.write(f"引用信息 {i}:\n{reference}\n\n")
            link_count = link_counts[i - 1]
            for j in range(link_count):  # 根据实际找到的链接数量写入
                if index < len(all_links):
                    link = all_links[index]
                    title = titles[index]
                    abstract = abstracts[index]
                    full_text_link = full_text_links[index]

                    file.write(f"论文 {i}.{j + 1}:\n")
                    file.write(f"链接: {link}\n")
                    if title:
                        file.write(f"标题: {title}\n")
                    else:
                        file.write("标题: 没有找到标题内容\n")

                    if abstract:
                        file.write(f"摘要: {abstract}\n")
                    else:
                        file.write("摘要: 没有找到摘要内容\n")

                    if full_text_link:
                        file.write(f"全文链接: {full_text_link}\n")
                    else:
                        file.write("全文链接: 没有找到全文链接\n")

                    file.write("\n" + "-" * 80 + "\n\n")
                    index += 1
                else:
                    break

    print(f"所有内容已保存到文件: {full_file_path}")
    progress_label.config(text="搜索完成！")
    root.after(2000, root.quit)

def start_search(progress_var, root):
    main(progress_var, root)

if __name__ == "__main__":
    # 创建主窗口
    root = tk.Tk()
    root.title("PubMed 论文搜索工具")
    root.geometry("300x100")

    # 创建进度条
    progress_var = tk.DoubleVar()
    progress_bar = ttk.Progressbar(root, variable=progress_var, maximum=85)
    progress_bar.pack(pady=20)

    # 创建进度标签
    progress_label = tk.Label(root, text="正在搜索...")
    progress_label.pack(pady=10)

    # 启动搜索线程
    search_thread = threading.Thread(target=start_search, args=(progress_var, root))
    search_thread.start()

    # 运行主循环
    root.mainloop()
