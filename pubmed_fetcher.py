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
            if entry:
                references.append(entry)
    return references


def search_pubmed(term):
    base_url = "https://pubmed.ncbi.nlm.nih.gov/"
    search_url = f"{base_url}?term={term}"
    response = requests.get(search_url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        article_links = soup.find_all('a', class_='docsum-title')
        links = [base_url + link['href'] for link in article_links[:10]]
        return links
    else:
        print(f"进入PubMed搜索结果页面失败，状态码: {response.status_code}")
        return []


def fetch_paper_details(link):
    article_response = requests.get(link)
    if article_response.status_code == 200:
        article_soup = BeautifulSoup(article_response.content, 'html.parser')
        # 查找摘要部分
        abstract_section = article_soup.find('div', {'class': 'abstract-content selected'})
        abstract_text = abstract_section.get_text(strip=True) if abstract_section else None

        # 查找标题部分
        title_section = article_soup.find('h1', {'class': 'heading-title'})
        title_text = title_section.get_text(strip=True) if title_section else None

        return title_text, abstract_text
    else:
        print(f"访问论文失败，状态码: {article_response.status_code}")
        return None, None


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

    # 总任务数
    total_tasks = len(references) * 10  # 假设每次搜索最多返回10篇论文
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
                title, abstract = fetch_paper_details(link)
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

                completed_tasks += 1
                progress_var.set((completed_tasks / total_tasks) * 100)
                root.update_idletasks()
                time.sleep(0.1)  # 模拟处理时间
        else:
            print(f"没有找到与引用信息 '{reference}' 相关的论文")
            titles.append(None)
            abstracts.append(None)
            completed_tasks += 10
            progress_var.set((completed_tasks / total_tasks) * 100)
            root.update_idletasks()
            time.sleep(0.1)  # 模拟处理时间

    # 获取当前时间作为文件名
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(os.getcwd(), "papers")
    file_name = f"papers_{current_time}.txt"
    full_file_path = os.path.join(file_path, file_name)

    # 确保文件夹存在
    os.makedirs(file_path, exist_ok=True)

    # 将摘要和标题内容写入文件
    with open(full_file_path, 'w', encoding='utf-8') as file:
        index = 0
        for i, reference in enumerate(references, start=1):
            file.write(f"引用信息 {i}:\n{reference}\n\n")
            for j in range(10):  # 假设每次搜索最多返回10篇论文
                if index < len(all_links):
                    link = all_links[index]
                    title = titles[index]
                    abstract = abstracts[index]

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

                    file.write("\n" + "-" * 80 + "\n\n")
                    index += 1
                else:
                    break

    print(f"所有内容已保存到文件: {full_file_path}")
    progress_label.config(text="搜索完成！")


def start_search(progress_var, root):
    main(progress_var, root)


if __name__ == "__main__":
    # 创建主窗口
    root = tk.Tk()
    root.title("PubMed 论文搜索工具")
    root.geometry("400x200")

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
