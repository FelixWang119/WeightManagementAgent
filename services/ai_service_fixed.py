    async def vision_analysis(
        self, image_url: str, prompt: str, model: Optional[str] = None
    ) -> AIResponse:
        """Qwen 图像分析 - 使用OpenAI兼容接口"""
        try:
            # 使用OpenAI兼容接口
            # 如果base_url已经包含compatible-mode/v1，直接使用
            if "compatible-mode/v1" in self.api_base:
                url = f"{self.api_base}/chat/completions"
            else:
                # 否则添加compatible-mode/v1路径
                url = f"{self.api_base}/compatible-mode/v1/chat/completions"

            # 尝试使用支持视觉的模型，如果未指定则使用默认
            vision_model = model or "qwen-vl-plus"
            
            # 检查是否是base64 data URL，如果不是则转换为base64
            if image_url.startswith("data:image"):
                # 已经是data URL格式
                image_content = image_url
            else:
                # 假设是文件URL，需要下载并转换为base64
                # 这里简化处理，实际应该下载图片
                image_content = image_url

            payload = {
                "model": vision_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": image_content}},
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
                "max_tokens": 1000,
            }

            print(f"Vision分析请求 - 模型: {vision_model}, URL: {url}")
            print(f"图片URL类型: {'data URL' if image_url.startswith('data:image') else '普通URL'}")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url, headers=self.headers, json=payload, timeout=60.0
                )
                response.raise_for_status()

                data = response.json()

                if "choices" in data and len(data["choices"]) > 0:
                    choice = data["choices"][0]
                    return AIResponse(
                        content=choice["message"]["content"],
                        model=data.get("model", vision_model),
                    )
                else:
                    return AIResponse(
                        content="",
                        model=vision_model,
                        error=f"Qwen Vision 响应格式错误: {data}",
                    )
        except httpx.HTTPError as e:
            # 记录Qwen Vision HTTP错误告警
            error_msg = str(e)
            alert_error(
                category=AlertCategory.AI_SERVICE,
                message="Qwen Vision API调用失败",
                details={
                    "model": model or "qwen-vl-plus",
                    "error": error_msg,
                    "endpoint": "compatible-mode/v1/chat/completions",
                    "provider": "qwen",
                    "feature": "vision_analysis",
                },
                module="ai_service.QwenClient",
            )
            
            # 检查是否是模型不支持的错误
            if "400" in error_msg and "model" in error_msg.lower():
                print(f"Vision模型可能不支持，错误: {error_msg}")
                return AIResponse(
                    content="",
                    model=model or "qwen-vl-plus",
                    error=f"Qwen Vision 模型不支持或配置错误: {error_msg}",
                )
            
            return AIResponse(
                content="",
                model=model or "qwen-vl-plus",
                error=f"Qwen Vision 错误: {error_msg}",
            )
        except Exception as e:
            # 记录Qwen Vision API错误告警
            error_msg = str(e)
            alert_error(
                category=AlertCategory.AI_SERVICE,
                message="Qwen Vision API调用失败",
                details={
                    "model": model or "qwen-vl-plus",
                    "error": error_msg,
                    "endpoint": "compatible-mode/v1/chat/completions",
                    "provider": "qwen",
                    "feature": "vision_analysis",
                },
                module="ai_service.QwenClient",
            )
            return AIResponse(
                content="",
                model=model or "qwen-vl-plus",
                error=f"Qwen Vision 错误: {error_msg}",
            )